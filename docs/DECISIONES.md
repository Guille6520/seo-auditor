# Decisiones, límites y plan

Registro de por qué el proyecto es como es. Fechas en formato AAAA-MM-DD.

## Nota sobre el historial de commits

El historial se organizó por capas a partir del código ya terminado (protección SSRF, descarga, parser, rastreador, comprobaciones, informes, CLI, documentación...), de modo que se lea en orden lógico y cada commit pase sus tests. No refleja el orden cronológico real del trabajo: todos los commits llevan la fecha de esa reorganización (16 de noviembre de 2026).

## Objetivo (2026-11-04)

Un auditor SEO sencillo y efectivo: una sola orden, resultados reproducibles, que corra sin depender de ningún servicio externo ni de una sesión de Claude Code. Funciona en local; la ejecución en GitHub Actions es opcional (ver decisión 4).

## Decisiones

1. **Núcleo determinista, sin LLM.** Las comprobaciones y la nota son código con tests. Motivo: si la nota la agregara un modelo, dos ejecuciones sobre el mismo sitio podrían diferir y no habría test que lo fije. Aquí cada hallazgo es reproducible y trae evidencia.
2. **Una orden para auditar y otra para comparar, no decenas.** Menos superficie que mantener. Aquí no hay integraciones externas que puedan romperse.
3. **Python + `requests` + `lxml`/`beautifulsoup4`.** Pocas dependencias, instalación trivial en Actions y en Windows.
4. **Ejecución local como uso principal; GitHub Actions solo manual (2026-11-04).** Inicialmente se planteó Actions con cron semanal. Se cambió porque en repositorios privados los minutos son una cuota compartida por todos los repositorios de la cuenta y no se quiere arriesgar el uso gratuito de otros proyectos. El workflow se conserva con `workflow_dispatch` únicamente (sin `schedule`): informe en el resumen del trabajo y como artefacto, entradas por variables de entorno, permisos mínimos. Alternativas valoradas: Programador de tareas de Windows para ejecución semanal local (el PC debe estar encendido) y repositorio público (minutos gratis sin límite, pero código e informes visibles).
5. **Pesos y umbrales propios y documentados** en [NOTA.md](NOTA.md); las comprobaciones que dependen de la red o de una práctica discutida pesan 0.
6. **Honestidad sobre lo no evaluado:** si el rastreo es incompleto, `orphan_pages` no puntúa en vez de dar falsos positivos.

## Problemas hallados al probar (resueltos)

- Una URL que redirigía a otra página ya rastreada se analizaba dos veces (aparecía duplicada en títulos y noindex). Ahora solo cuenta como redirección.
- Los espacios internos repetidos en títulos y descripciones no se colapsaban (`"Hola  mundo"`). Ahora se normalizan.

## Límites conocidos

- Sin renderizado de JavaScript: sitios que pintan el contenido en el cliente salen con poco texto y pocos enlaces.
- Sin Core Web Vitals reales ni medición de rendimiento de usuario.
- Sin validación semántica de schema.org.
- DNS rebinding: ver [ARQUITECTURA.md](ARQUITECTURA.md#seguridad).
- El rastreo es secuencial; con `max_pages` 50 y pausa de 0,2 s tarda del orden de minutos en sitios lentos.
- Probado con servidores locales de pruebas y, la versión 0.2.0, contra tres sitios reales (python.org, gnu.org y Wikipedia en español), comprobando a mano una muestra de hallazgos. No se ha contrastado la precisión frente a otras herramientas.
- Un `noindex` intencionado (por ejemplo, páginas de búsqueda) resta nota igual que uno olvidado: el programa no puede saber la intención.

## Segunda vuelta (2026-11-14)

- **Informe HTML** (`report_html.py`): autocontenido y sin JavaScript, para poder enviarlo o abrirlo sin servidor. Como los datos vienen de sitios de terceros, se escapa todo y solo se enlazan URLs http(s).
- **Comparación antes/después** (`history.py`, subcomando `compare`): es una función pura sobre dos `informe.json`. Compara recuentos absolutos de fallos y avisa cuando los informes no son homogéneos en lugar de negarse a comparar.
- **Demostración reproducible** (`demo/`): un sitio de ejemplo local en dos versiones, para enseñar el auditor sin depender de webs ajenas. El vídeo se graba con un script que ejecuta el programa de verdad; nada de lo que se ve está escrito a mano.
- **Revisión independiente del código**, cuyos hallazgos confirmados se corrigieron con su test (ver el historial de commits).
- **Textos con tildes** en los informes.

## Plan

Orden previsto, cada paso independiente:

1. **Histórico automático:** guardar cada `informe.json` con fecha y comparar con el anterior sin indicar los ficheros a mano.
2. **Capa opcional con Claude:** que el modelo solo redacte y priorice las 10 mejoras principales a partir del JSON, con la clave de API como secreto del repositorio. La nota nunca dependería de ella.
3. **Parches generados:** JSON-LD listo para pegar, `robots.txt`, `llms.txt`, redirecciones.
3. **PageSpeed/CrUX** (API gratuita de Google) para Core Web Vitals reales.
4. **Renderizado opcional con Playwright** para sitios con JavaScript.
5. **Informe en español para cliente** (HTML con marca propia) y publicación en GitHub Pages.
6. **Web o bot de Telegram** sobre el mismo núcleo; antes habría que fijar la IP resuelta (SSRF) y limitar peticiones por usuario.
