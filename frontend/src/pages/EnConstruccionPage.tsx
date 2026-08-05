import { SinDatos } from '@/components/Feedback'

/**
 * Placeholder honesto para las secciones que llegan en fases siguientes.
 *
 * Se prefiere esto a ocultar el enlace del menú: así la navegación completa ya
 * es navegable y probable, y queda claro qué falta en vez de parecer roto.
 */
export function EnConstruccionPage({ titulo, fase }: { titulo: string; fase: string }) {
  return (
    <section className="pagina">
      <h1>{titulo}</h1>
      <SinDatos
        titulo="Todavía no está disponible"
        detalle={`Esta sección llega en la ${fase}.`}
      />
    </section>
  )
}
