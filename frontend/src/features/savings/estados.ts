import type { GoalStatus } from '@/types/api'

/** Compartido entre la tarjeta y el resumen del dashboard para que una meta no
 *  se llame «Vas tarde» en una pantalla y otra cosa en la otra. */
export const ETIQUETA_DE_ESTADO: Record<GoalStatus, string> = {
  ON_TRACK: 'En camino',
  AT_RISK: 'Vas tarde',
  ACHIEVED: 'Alcanzada',
}
