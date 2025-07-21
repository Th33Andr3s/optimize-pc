import os
import shutil
import tempfile
import subprocess
import sys
from pathlib import Path
import time

class PCOptimizer:
    def __init__(self):
        self.total_freed = 0
        self.cleaned_locations = []
        
    def get_size_format(self, size_bytes):
        """Convierte bytes a formato legible"""
        if size_bytes == 0:
            return "0 B"
        size_names = ["B", "KB", "MB", "GB"]
        i = 0
        while size_bytes >= 1024 and i < len(size_names) - 1:
            size_bytes /= 1024.0
            i += 1
        return f"{size_bytes:.2f} {size_names[i]}"
    
    def get_folder_size(self, folder_path):
        """Calcula el tamaño total de una carpeta"""
        total_size = 0
        try:
            for dirpath, dirnames, filenames in os.walk(folder_path):
                for filename in filenames:
                    file_path = os.path.join(dirpath, filename)
                    try:
                        total_size += os.path.getsize(file_path)
                    except (OSError, FileNotFoundError):
                        continue
        except (OSError, PermissionError):
            pass
        return total_size
    
    def clean_temp_files(self):
        """Limpia archivos temporales del sistema"""
        print("🧹 Limpiando archivos temporales...")
        
        temp_dirs = [
            tempfile.gettempdir(),
            os.path.expandvars(r'%USERPROFILE%\AppData\Local\Temp'),
            os.path.expandvars(r'%WINDIR%\Temp'),
            os.path.expandvars(r'%TEMP%'),
            os.path.expandvars(r'%TMP%')
        ]
        
        cleaned_size = 0
        
        for temp_dir in temp_dirs:
            if os.path.exists(temp_dir):
                size_before = self.get_folder_size(temp_dir)
                cleaned_files = self._clean_directory(temp_dir)
                size_after = self.get_folder_size(temp_dir)
                freed = size_before - size_after
                cleaned_size += freed
                
                if cleaned_files > 0:
                    self.cleaned_locations.append(f"📁 {temp_dir}: {cleaned_files} archivos, {self.get_size_format(freed)} liberados")
        
        self.total_freed += cleaned_size
        print(f"✅ Archivos temporales: {self.get_size_format(cleaned_size)} liberados")
    
    def clean_browser_cache(self):
        """Limpia caché de navegadores populares"""
        print("🌐 Limpiando caché de navegadores...")
        
        browser_paths = {
            'Chrome': [
                os.path.expandvars(r'%USERPROFILE%\AppData\Local\Google\Chrome\User Data\Default\Cache'),
                os.path.expandvars(r'%USERPROFILE%\AppData\Local\Google\Chrome\User Data\Default\Code Cache')
            ],
            'Firefox': [
                os.path.expandvars(r'%USERPROFILE%\AppData\Local\Mozilla\Firefox\Profiles')
            ],
            'Edge': [
                os.path.expandvars(r'%USERPROFILE%\AppData\Local\Microsoft\Edge\User Data\Default\Cache')
            ]
        }
        
        cleaned_size = 0
        
        for browser, paths in browser_paths.items():
            for path in paths:
                if 'Firefox' in browser and os.path.exists(path):
                    # Firefox tiene una estructura especial
                    for profile in os.listdir(path):
                        profile_path = os.path.join(path, profile, 'cache2')
                        if os.path.exists(profile_path):
                            size_before = self.get_folder_size(profile_path)
                            cleaned_files = self._clean_directory(profile_path)
                            freed = size_before - self.get_folder_size(profile_path)
                            cleaned_size += freed
                            if cleaned_files > 0:
                                self.cleaned_locations.append(f"🦊 Firefox Cache: {cleaned_files} archivos, {self.get_size_format(freed)} liberados")
                elif os.path.exists(path):
                    size_before = self.get_folder_size(path)
                    cleaned_files = self._clean_directory(path)
                    freed = size_before - self.get_folder_size(path)
                    cleaned_size += freed
                    if cleaned_files > 0:
                        self.cleaned_locations.append(f"🌐 {browser} Cache: {cleaned_files} archivos, {self.get_size_format(freed)} liberados")
        
        self.total_freed += cleaned_size
        print(f"✅ Caché de navegadores: {self.get_size_format(cleaned_size)} liberados")
    
    def clean_windows_cache(self):
        """Limpia caché específico de Windows"""
        print("🪟 Limpiando caché de Windows...")
        
        windows_cache_dirs = [
            os.path.expandvars(r'%USERPROFILE%\AppData\Local\Microsoft\Windows\INetCache'),
            os.path.expandvars(r'%USERPROFILE%\AppData\Local\Microsoft\Windows\WebCache'),
            os.path.expandvars(r'%WINDIR%\SoftwareDistribution\Download'),
            os.path.expandvars(r'%USERPROFILE%\AppData\Local\CrashDumps'),
            os.path.expandvars(r'%WINDIR%\Logs'),
            os.path.expandvars(r'%USERPROFILE%\AppData\Local\IconCache.db')
        ]
        
        cleaned_size = 0
        
        for cache_dir in windows_cache_dirs:
            if os.path.exists(cache_dir):
                if os.path.isfile(cache_dir):
                    # Es un archivo específico
                    try:
                        file_size = os.path.getsize(cache_dir)
                        os.remove(cache_dir)
                        cleaned_size += file_size
                        self.cleaned_locations.append(f"🗑️ {os.path.basename(cache_dir)}: {self.get_size_format(file_size)} liberados")
                    except (OSError, PermissionError):
                        continue
                else:
                    # Es un directorio
                    size_before = self.get_folder_size(cache_dir)
                    cleaned_files = self._clean_directory(cache_dir)
                    freed = size_before - self.get_folder_size(cache_dir)
                    cleaned_size += freed
                    if cleaned_files > 0:
                        self.cleaned_locations.append(f"🪟 {os.path.basename(cache_dir)}: {cleaned_files} archivos, {self.get_size_format(freed)} liberados")
        
        self.total_freed += cleaned_size
        print(f"✅ Caché de Windows: {self.get_size_format(cleaned_size)} liberados")
    
    def clean_recycle_bin(self):
        """Vacía la papelera de reciclaje"""
        print("🗑️ Vaciando papelera de reciclaje...")
        
        try:
            # Usando PowerShell para vaciar la papelera
            result = subprocess.run([
                'powershell', '-Command',
                'Clear-RecycleBin -Confirm:$false'
            ], capture_output=True, text=True, shell=True)
            
            if result.returncode == 0:
                print("✅ Papelera de reciclaje vaciada")
                self.cleaned_locations.append("🗑️ Papelera de reciclaje vaciada")
            else:
                print("⚠️ No se pudo vaciar la papelera automáticamente")
        except Exception as e:
            print(f"⚠️ Error al vaciar papelera: {e}")
    
    def _clean_directory(self, directory_path):
        """Limpia archivos de un directorio específico"""
        cleaned_files = 0
        
        try:
            for root, dirs, files in os.walk(directory_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    try:
                        os.remove(file_path)
                        cleaned_files += 1
                    except (OSError, PermissionError, FileNotFoundError):
                        continue
                
                # Intentar eliminar directorios vacíos
                for dir in dirs:
                    dir_path = os.path.join(root, dir)
                    try:
                        if not os.listdir(dir_path):
                            os.rmdir(dir_path)
                    except (OSError, PermissionError):
                        continue
                        
        except (OSError, PermissionError):
            pass
            
        return cleaned_files
    
    def run_disk_cleanup(self):
        """Ejecuta el limpiador de disco de Windows"""
        print("💿 Ejecutando limpiador de disco de Windows...")
        
        try:
            subprocess.run(['cleanmgr', '/sagerun:1'], shell=True)
            print("✅ Limpiador de disco ejecutado")
            self.cleaned_locations.append("💿 Limpiador de disco de Windows ejecutado")
        except Exception as e:
            print(f"⚠️ No se pudo ejecutar el limpiador de disco: {e}")
    
    def optimize(self, include_disk_cleanup=False):
        """Ejecuta todas las operaciones de optimización"""
        print("=" * 50)
        print("🚀 INICIANDO OPTIMIZACIÓN DE PC")
        print("=" * 50)
        
        start_time = time.time()
        
        # Limpiezas principales
        self.clean_temp_files()
        self.clean_browser_cache()
        self.clean_windows_cache()
        self.clean_recycle_bin()
        
        if include_disk_cleanup:
            self.run_disk_cleanup()
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Reporte final
        print("\n" + "=" * 50)
        print("📊 REPORTE DE OPTIMIZACIÓN")
        print("=" * 50)
        print(f"⏱️ Tiempo total: {duration:.2f} segundos")
        print(f"💾 Espacio total liberado: {self.get_size_format(self.total_freed)}")
        print(f"📁 Ubicaciones limpiadas: {len(self.cleaned_locations)}")
        
        if self.cleaned_locations:
            print("\n📋 Detalle de limpieza:")
            for location in self.cleaned_locations:
                print(f"  {location}")
        
        print("\n✨ ¡Optimización completada!")
        print("=" * 50)

def main():
    """Función principal"""
    print("🔧 Optimizador de PC - Limpiador de Archivos")
    print("⚠️  ADVERTENCIA: Este programa eliminará archivos. Asegúrate de cerrar todos los programas.")
    
    response = input("\n¿Deseas continuar? (s/n): ").lower().strip()
    
    if response not in ['s', 'si', 'sí', 'y', 'yes']:
        print("❌ Operación cancelada.")
        return
    
    disk_cleanup = input("\n¿Incluir limpiador de disco de Windows? (s/n): ").lower().strip()
    include_cleanup = disk_cleanup in ['s', 'si', 'sí', 'y', 'yes']
    
    try:
        optimizer = PCOptimizer()
        optimizer.optimize(include_disk_cleanup=include_cleanup)
        
        input("\n📱 Presiona Enter para salir...")
        
    except KeyboardInterrupt:
        print("\n\n❌ Operación interrumpida por el usuario.")
    except Exception as e:
        print(f"\n❌ Error durante la optimización: {e}")
        input("Presiona Enter para salir...")

if __name__ == "__main__":
    # Verificar si se ejecuta como administrador (recomendado)
    try:
        is_admin = os.getuid() == 0
    except AttributeError:
        # Windows
        import ctypes
        try:
            is_admin = ctypes.windll.shell32.IsUserAnAdmin()
        except:
            is_admin = False
    
    if not is_admin:
        print("⚠️ Se recomienda ejecutar como administrador para mejores resultados.")
    
    main()