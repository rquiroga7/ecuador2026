// Configuración del dashboard.
//
// El publicador local sube "datos_web.json" a la rama `data` del repositorio y el
// dashboard lo lee con cache-busting. Al crear el repositorio de Ecuador, apuntá
// esta URL a la rama `data` de tu repo, por ejemplo:
//
//   window.DATOS_URL = "https://raw.githubusercontent.com/<usuario>/<repo>/data/datos_web.json";
//
// Por defecto usa el archivo local `datos_web.json` (útil para desarrollo).
window.DATOS_URL = "datos_web.json";
