# FORJA Human Console UX Blueprint

Fase: Human Console Fase 1 - Apple-grade UX Blueprint Only  
Estado: Diseño para revisión humana, sin avance a fase 2

## 1. Visión general

La cabina humana de FORJA debe ser la entrada principal para que un CEO u operador humano pida construcción de tecnología con lenguaje natural. En menos de 5 segundos debe entender:

> Aquí le puedo pedir que construya algo.

La experiencia no debe iniciar con telemetría, módulos internos ni lenguaje DevOps. Debe iniciar con una consola humana, amplia y premium, que diga claramente qué puede pedir el usuario:

- una app
- una API
- un dashboard
- un módulo
- un workflow
- una integración

La cabina debe transmitir poder controlado: FORJA puede planear y construir, pero las acciones técnicas sensibles quedan protegidas detrás de governance, approvals y revisión humana.

## 2. Usuario objetivo

Usuario principal: CEO u operador humano de 35 a 45 años.

Perfil:

- Quiere pedir resultados, no administrar infraestructura.
- Valora claridad, control, confianza y velocidad.
- No quiere leer logs técnicos como primer contacto.
- Necesita ver que FORJA entiende su intención y puede convertirla en plan.
- Debe sentir que el sistema es fuerte, serio y premium, no improvisado.

## 3. Emoción que debe transmitir

FORJA debe sentirse como:

- producto hecho por Apple
- control room elegante
- dashboard tipo Tesla, pero para construir software
- estudio premium de creación tecnológica
- fábrica inteligente con poder contenido
- herramienta fuerte, sobria, confiable y lista para operar

La emoción central es: "Puedo pedir algo grande y el sistema lo convierte en una ruta clara, controlada y revisable".

## 4. Flujo principal

Flujo de la experiencia humana:

1. El CEO abre FORJA.
2. Ve una cabina limpia con una promesa directa: "Pide una app, API, dashboard, módulo, workflow o integración".
3. Escribe una petición en un input grande.
4. Puede elegir botones rápidos con intenciones comunes.
5. FORJA muestra una respuesta ejemplo: entendió el pedido, lo clasificó y propone un siguiente paso.
6. FORJA muestra un plan generado ejemplo con fases visibles.
7. El panel técnico aparece colapsado y no compite con la experiencia humana.
8. El CEO decide si la visión visual se aprueba para diseñar fase 2.

En esta fase, el flujo es visual y conceptual. No ejecuta construcción real.

## 5. Jerarquía visual

Prioridad de pantalla:

1. Hero humano con FORJA como cabina de construcción.
2. Input grande, central y táctil.
3. Botones rápidos de intención.
4. Estado de confianza: "Preview visual, sin ejecución real".
5. Respuesta ejemplo de FORJA.
6. Plan generado ejemplo.
7. Panel técnico colapsado.
8. Enlaces o datos técnicos secundarios.

La pantalla principal no debe abrir con paneles de runtime, provider health, audit stream o execution logs. Eso debe existir, pero detrás de una sección colapsada o una pestaña técnica.

## 6. Paleta

Paleta recomendada:

- Carbón profundo: `#080706`, `#12100e`
- Hierro oscuro: `#1d1815`, `#24201d`
- Cobre: `#b76436`
- Brasa: `#e46d33`
- Rojo forja elegante: `#8f2f22`
- Dorado tenue: `#d6a15b`
- Marfil técnico: `#fff3e5`
- Gris humo: `#aaa099`

Reglas:

- El cobre y la brasa son acentos, no fondos dominantes.
- El rojo no debe parecer alerta de casino ni rojo sangre.
- El dorado debe sentirse sutil y caro.
- El contraste debe ser alto para lectura rápida.

## 7. Tipografía recomendada

Usar stack del sistema para mantener sensación Apple-grade:

```css
Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "SF Pro Display", "Segoe UI", sans-serif
```

Uso recomendado:

- H1: grande, fuerte, humano, sin tecnicismos.
- Subtexto: claro, cálido, con beneficios.
- Botones: texto corto y directo.
- Panel técnico: tipografía más compacta, secundaria.

Evitar:

- textos microscópicos
- exceso de mayúsculas
- labels técnicos como primer nivel de lectura
- inglés como idioma principal

## 8. Microinteracciones

Microinteracciones deseadas:

- Botones con elevación sutil al hover.
- Presión táctil suave en active.
- Glow de brasa muy controlado en foco.
- Input grande con borde cobre y sombra interna.
- Botones rápidos con selección visual clara.
- Panel técnico colapsado con transición suave.
- Plan generado con pasos que parezcan placas metálicas pulidas.

No usar:

- animaciones exageradas
- parpadeos agresivos
- efectos tipo juego
- saturación de luces

## 9. Botones

Botón primario:

- Debe sentirse físico, 3D/4D premium.
- Fondo carbón/cobre con highlight superior.
- Sombra inferior controlada.
- Texto claro: "Generar plan visual", "Diseñar app", "Crear API".

Botones rápidos:

- Deben parecer chips premium, no tags baratos.
- Deben decir cosas humanas:
  - Crear una app
  - Diseñar una API
  - Armar un dashboard
  - Crear workflow
  - Integrar sistema

Botones técnicos:

- Secundarios.
- No deben dominar el primer viewport.

## 10. Mobile-first

En mobile:

- El input debe ser el centro de la experiencia.
- Los botones rápidos deben apilarse sin romper layout.
- El plan ejemplo debe leerse en una columna.
- El panel técnico debe permanecer colapsado.
- La experiencia debe sentirse como app premium, no como web apretada.

Regla: a 390 px de ancho no debe existir overflow horizontal.

## 11. Accesibilidad

Criterios:

- Contraste alto en texto principal.
- Labels claros en input.
- Botones con `type="button"` si no ejecutan submit.
- Foco visible.
- Panel técnico con `<details>` y `<summary>` para accesibilidad nativa.
- No depender solo del color para indicar estado.
- Textos principales en español.

## 12. Qué se oculta como técnico

Debe quedar oculto o secundario:

- runtime status
- provider state
- command statuses
- capability internals
- audit stream
- execution logs
- output manager
- governance internals
- render/cloud details
- endpoints técnicos

No se elimina. Se reubica como:

- "Panel técnico"
- "Detalles de control"
- "Ver estado avanzado"
- "Auditoría y runtime"

## 13. Qué queda visible al CEO

Visible en primer nivel:

- FORJA como marca.
- Mensaje: "Pídele a FORJA que construya".
- Input grande.
- Botones rápidos.
- Respuesta ejemplo.
- Plan ejemplo.
- Nota clara: "Preview visual, sin ejecución real".
- Estado de confianza: "Control humano activo".

## 14. Preview de Fase 1

La preview debe ser una maqueta funcional solo para revisión visual. No debe ejecutar ni conectar lógica nueva.

Debe mostrar:

- hero humano
- input grande
- botones rápidos
- ejemplo de respuesta
- ejemplo de plan generado
- panel técnico oculto/colapsado
- estética Apple-grade forja

Ruta propuesta:

- `/#human-console-preview`

Texto de seguridad visible:

- "Preview visual. No ejecuta construcción real."
- "Control humano siempre activo."
- "Panel técnico colapsado para no distraer al CEO."

## 15. Criterios de aprobación visual

La fase 1 se aprueba si:

- En 5 segundos se entiende que FORJA sirve para pedir construcción tecnológica.
- La pantalla se siente premium, fuerte y humana.
- La experiencia principal está en español.
- La UI no parece DevOps como pantalla principal.
- El dashboard técnico actual sigue disponible.
- No hay ejecución real ni lógica nueva de construcción.
- No se tocó backend, governance, execution engine, output manager, capability system, Render config ni secrets.
- `npm run build` pasa.
- No hay errores de consola en la preview.
- Mobile no tiene overflow horizontal.

## 16. Límites explícitos de esta fase

Esta fase no incluye:

- conexión real de input a execution engine
- creación real de apps/APIs/módulos
- cambios backend
- cambios governance
- cambios output manager
- cambios capability system
- deploy
- fase 2

La siguiente fase solo debe iniciar con aprobación explícita del CEO.
