import os
import ctypes
import tempfile
import subprocess
import time


class PCOptimizer:
    """Herramienta para limpiar archivos temporales, cache y basura en Windows."""

    def __init__(self):
        # Acumulador del espacio total liberado en bytes
        self.total_freed = 0
        # Registro descriptivo de cada ubicacion limpiada
        self.cleaned_locations = []

    # -- Utilidades ----------------------------------------------------------

    @staticmethod
    def format_size(size_bytes):
        """Convierte una cantidad en bytes a formato legible (KB, MB, GB)."""
        if size_bytes == 0:
            return "0 B"
        units = ("B", "KB", "MB", "GB")
        index = 0
        size = float(size_bytes)
        while size >= 1024.0 and index < len(units) - 1:
            size /= 1024.0
            index += 1
        return f"{size:.2f} {units[index]}"

    def _clean_directory(self, directory_path):
        """
        Elimina recursivamente los archivos de un directorio y luego
        intenta borrar los subdirectorios que queden vacios.

        Usa topdown=False para recorrer desde las carpetas mas profundas
        hacia arriba, lo que permite eliminar subdirectorios vacios
        correctamente en un solo recorrido.

        Retorna (archivos_eliminados, bytes_liberados).
        """
        cleaned_files = 0
        freed_bytes = 0

        try:
            for root, dirs, files in os.walk(directory_path, topdown=False):
                # Eliminar archivos
                for filename in files:
                    file_path = os.path.join(root, filename)
                    try:
                        file_size = os.path.getsize(file_path)
                        os.remove(file_path)
                        cleaned_files += 1
                        freed_bytes += file_size
                    except (OSError, PermissionError, FileNotFoundError):
                        # El archivo puede estar en uso o protegido
                        continue

                # Eliminar subdirectorios vacios (solo funciona si estan vacios)
                for dirname in dirs:
                    dir_path = os.path.join(root, dirname)
                    try:
                        os.rmdir(dir_path)
                    except (OSError, PermissionError):
                        continue

        except (OSError, PermissionError):
            pass

        return cleaned_files, freed_bytes

    def _record_cleaned(self, label, cleaned_files, freed_bytes):
        """Registra una ubicacion limpiada si se eliminaron archivos."""
        if cleaned_files > 0:
            self.cleaned_locations.append(
                f"  {label}: {cleaned_files} archivos, "
                f"{self.format_size(freed_bytes)} liberados"
            )

    # -- Modulos de limpieza -------------------------------------------------

    def clean_temp_files(self):
        """
        Limpia los directorios de archivos temporales del sistema.

        Varias variables de entorno (%TEMP%, %TMP%, etc.) suelen apuntar
        al mismo directorio. Se usa un conjunto (set) con rutas resueltas
        para evitar limpiar el mismo directorio mas de una vez.
        """
        print("[*] Limpiando archivos temporales...")

        # Recopilar candidatos de directorios temporales
        temp_candidates = [
            tempfile.gettempdir(),
            os.path.expandvars(r"%USERPROFILE%\AppData\Local\Temp"),
            os.path.expandvars(r"%WINDIR%\Temp"),
            os.path.expandvars(r"%TEMP%"),
            os.path.expandvars(r"%TMP%"),
        ]

        # Resolver rutas reales y eliminar duplicados
        seen = set()
        temp_dirs = []
        for path in temp_candidates:
            resolved = os.path.realpath(path)
            if resolved not in seen and os.path.isdir(resolved):
                seen.add(resolved)
                temp_dirs.append(resolved)

        cleaned_size = 0
        for temp_dir in temp_dirs:
            cleaned_files, freed = self._clean_directory(temp_dir)
            cleaned_size += freed
            self._record_cleaned(temp_dir, cleaned_files, freed)

        self.total_freed += cleaned_size
        print(f"[OK] Archivos temporales: {self.format_size(cleaned_size)} liberados")

    def clean_browser_cache(self):
        """Limpia la cache de Chrome, Firefox y Edge."""
        print("[*] Limpiando cache de navegadores...")

        user_profile = os.environ.get("USERPROFILE", "")
        local_appdata = os.path.join(user_profile, "AppData", "Local")

        # Rutas de cache por navegador
        browser_paths = {
            "Chrome": [
                os.path.join(local_appdata, r"Google\Chrome\User Data\Default\Cache"),
                os.path.join(local_appdata, r"Google\Chrome\User Data\Default\Code Cache"),
            ],
            "Edge": [
                os.path.join(local_appdata, r"Microsoft\Edge\User Data\Default\Cache"),
            ],
        }

        cleaned_size = 0

        # Limpiar Chrome y Edge (estructura directa de cache)
        for browser, paths in browser_paths.items():
            for path in paths:
                if not os.path.isdir(path):
                    continue
                cleaned_files, freed = self._clean_directory(path)
                cleaned_size += freed
                self._record_cleaned(f"{browser} Cache", cleaned_files, freed)

        # Limpiar Firefox (estructura especial con perfiles)
        cleaned_size += self._clean_firefox_profiles(local_appdata)

        self.total_freed += cleaned_size
        print(f"[OK] Cache de navegadores: {self.format_size(cleaned_size)} liberados")

    def _clean_firefox_profiles(self, local_appdata):
        """
        Limpia la cache de todos los perfiles de Firefox.

        Firefox almacena cada perfil en un subdirectorio dentro de Profiles/,
        y la cache se encuentra en la subcarpeta 'cache2' de cada perfil.
        Retorna el total de bytes liberados.
        """
        profiles_path = os.path.join(local_appdata, r"Mozilla\Firefox\Profiles")
        total_freed = 0

        if not os.path.isdir(profiles_path):
            return 0

        try:
            for profile in os.listdir(profiles_path):
                cache_path = os.path.join(profiles_path, profile, "cache2")
                if os.path.isdir(cache_path):
                    cleaned_files, freed = self._clean_directory(cache_path)
                    total_freed += freed
                    self._record_cleaned(
                        f"Firefox Cache ({profile})", cleaned_files, freed
                    )
        except (OSError, PermissionError):
            pass

        return total_freed

    def clean_windows_cache(self):
        """
        Limpia cache y archivos temporales propios de Windows:
        cache de Internet Explorer, WebCache, descargas de Windows Update,
        volcados de errores (CrashDumps), logs del sistema e IconCache.
        """
        print("[*] Limpiando cache de Windows...")

        user_profile = os.environ.get("USERPROFILE", "")
        windir = os.environ.get("WINDIR", r"C:\Windows")

        # Directorios que se pueden limpiar de forma segura
        cache_dirs = [
            os.path.join(user_profile, r"AppData\Local\Microsoft\Windows\INetCache"),
            os.path.join(user_profile, r"AppData\Local\Microsoft\Windows\WebCache"),
            os.path.join(windir, r"SoftwareDistribution\Download"),
            os.path.join(user_profile, r"AppData\Local\CrashDumps"),
            os.path.join(windir, "Logs"),
        ]

        # Archivos individuales que se pueden eliminar
        cache_files = [
            os.path.join(user_profile, r"AppData\Local\IconCache.db"),
        ]

        cleaned_size = 0

        # Limpiar directorios
        for cache_dir in cache_dirs:
            if os.path.isdir(cache_dir):
                cleaned_files, freed = self._clean_directory(cache_dir)
                cleaned_size += freed
                self._record_cleaned(
                    os.path.basename(cache_dir), cleaned_files, freed
                )

        # Eliminar archivos individuales
        for cache_file in cache_files:
            if os.path.isfile(cache_file):
                try:
                    file_size = os.path.getsize(cache_file)
                    os.remove(cache_file)
                    cleaned_size += file_size
                    self.cleaned_locations.append(
                        f"  {os.path.basename(cache_file)}: "
                        f"{self.format_size(file_size)} liberados"
                    )
                except (OSError, PermissionError):
                    continue

        self.total_freed += cleaned_size
        print(f"[OK] Cache de Windows: {self.format_size(cleaned_size)} liberados")

    def clean_recycle_bin(self):
        """Vacia la papelera de reciclaje usando PowerShell."""
        print("[*] Vaciando papelera de reciclaje...")

        try:
            # Se evita shell=True por seguridad; se pasa el comando como lista
            result = subprocess.run(
                ["powershell", "-Command", "Clear-RecycleBin -Confirm:$false"],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                print("[OK] Papelera de reciclaje vaciada")
                self.cleaned_locations.append("  Papelera de reciclaje vaciada")
            else:
                print("[AVISO] No se pudo vaciar la papelera automaticamente")
        except Exception as e:
            print(f"[ERROR] Error al vaciar papelera: {e}")

    def run_disk_cleanup(self):
        """
        Ejecuta la utilidad de limpieza de disco de Windows (cleanmgr).
        Usa /sagerun:1 para ejecutar con la configuracion guardada
        previamente con /sageset:1.
        """
        print("[*] Ejecutando limpiador de disco de Windows...")

        try:
            subprocess.run(["cleanmgr", "/sagerun:1"])
            print("[OK] Limpiador de disco ejecutado")
            self.cleaned_locations.append("  Limpiador de disco de Windows ejecutado")
        except Exception as e:
            print(f"[ERROR] No se pudo ejecutar el limpiador de disco: {e}")

    def shutdown_pc(self, countdown=10):
        """
        Apaga el equipo despues de una cuenta regresiva.
        El usuario puede cancelar con Ctrl+C durante la cuenta.
        """
        print(f"\n[*] Apagando PC en {countdown} segundos...")
        print("[AVISO] Presiona Ctrl+C para cancelar el apagado")

        try:
            for i in range(countdown, 0, -1):
                print(f"  Apagado en {i} segundos...", end="\r")
                time.sleep(1)

            print("\n[*] Apagando PC ahora...")
            # /s = apagar, /f = forzar cierre de apps, /t 0 = sin espera adicional
            subprocess.run(["shutdown", "/s", "/f", "/t", "0"])

        except KeyboardInterrupt:
            print("\n\n[CANCELADO] Apagado cancelado por el usuario.")
            return False

        return True

    # -- Orquestador principal -----------------------------------------------

    def optimize(self, include_disk_cleanup=False, shutdown_after=False):
        """
        Ejecuta todos los modulos de limpieza en secuencia
        y muestra un reporte con el resultado total.
        """
        separator = "=" * 50

        print(separator)
        print("  INICIANDO OPTIMIZACION DE PC")
        print(separator)

        start_time = time.time()

        # Ejecutar cada modulo de limpieza en orden
        self.clean_temp_files()
        self.clean_browser_cache()
        self.clean_windows_cache()
        self.clean_recycle_bin()

        if include_disk_cleanup:
            self.run_disk_cleanup()

        elapsed = time.time() - start_time

        # Reporte final
        print()
        print(separator)
        print("  REPORTE DE OPTIMIZACION")
        print(separator)
        print(f"  Tiempo total: {elapsed:.2f} segundos")
        print(f"  Espacio total liberado: {self.format_size(self.total_freed)}")
        print(f"  Ubicaciones limpiadas: {len(self.cleaned_locations)}")

        if self.cleaned_locations:
            print()
            print("  Detalle de limpieza:")
            for location in self.cleaned_locations:
                print(f"    {location}")

        print()
        print("[OK] Optimizacion completada.")
        print(separator)

        # Apagar si el usuario lo solicito
        if shutdown_after:
            self.shutdown_pc(countdown=10)


# -- Funciones auxiliares ----------------------------------------------------


def is_admin():
    """Verifica si el script se esta ejecutando con privilegios de administrador."""
    try:
        # En sistemas tipo Unix
        return os.getuid() == 0
    except AttributeError:
        # En Windows, usar la API de Win32
        try:
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except (AttributeError, OSError):
            return False


def ask_yes_no(prompt):
    """
    Muestra una pregunta al usuario y retorna True si la respuesta
    es afirmativa (s, si, y, yes). Cualquier otra cosa retorna False.
    """
    answer = input(prompt).lower().strip()
    return answer in ("s", "si", "y", "yes")


def main():
    """Punto de entrada. Muestra un menu interactivo y ejecuta la optimizacion."""
    print("Optimizador de PC - Limpiador de Archivos")
    print("ADVERTENCIA: Este programa eliminara archivos temporales y cache.")
    print("Asegurate de cerrar todos los programas antes de continuar.")

    if not ask_yes_no("\nDeseas continuar? (s/n): "):
        print("Operacion cancelada.")
        return

    include_cleanup = ask_yes_no("Incluir limpiador de disco de Windows? (s/n): ")
    do_shutdown = ask_yes_no("Apagar la PC al finalizar? (s/n): ")

    try:
        optimizer = PCOptimizer()
        optimizer.optimize(
            include_disk_cleanup=include_cleanup,
            shutdown_after=do_shutdown,
        )

        if not do_shutdown:
            input("\nPresiona Enter para salir...")

    except KeyboardInterrupt:
        print("\n\nOperacion interrumpida por el usuario.")
    except Exception as e:
        print(f"\nError durante la optimizacion: {e}")
        input("Presiona Enter para salir...")


if __name__ == "__main__":
    if not is_admin():
        print(
            "[AVISO] Se recomienda ejecutar como administrador"
            " para mejores resultados.\n"
        )
    main()
