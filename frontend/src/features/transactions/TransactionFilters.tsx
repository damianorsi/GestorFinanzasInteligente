import { FormField } from '@/components/FormField'
import { SelectField } from '@/components/SelectField'
import { useCategorias } from '@/features/categories/api'
import type { TransactionType } from '@/types/api'

import { FILTROS_VACIOS } from './api'
import type { FiltrosDeMovimientos } from './api'

interface TransactionFiltersProps {
  filtros: FiltrosDeMovimientos
  onCambiar: (filtros: FiltrosDeMovimientos) => void
}

export function TransactionFilters({ filtros, onCambiar }: TransactionFiltersProps) {
  const categorias = useCategorias()

  const actualizar = (parcial: Partial<FiltrosDeMovimientos>) => {
    // Los valores vacíos se sacan del objeto en vez de mandarse vacíos: el
    // cliente HTTP los omitiría igual, pero así la clave de caché de la query
    // no cambia por escribir y borrar un filtro.
    const combinado = { ...filtros, ...parcial }
    const limpio = Object.fromEntries(
      Object.entries(combinado).filter(
        ([, valor]) => valor !== undefined && valor !== '' && valor !== null,
      ),
    )
    onCambiar(limpio as FiltrosDeMovimientos)
  }

  const hayFiltros = Object.keys(filtros).length > 0

  return (
    <section className="filtros" aria-label="Filtros">
      <div className="filtros__campos">
        <FormField
          id="filtro-desde"
          label="Desde"
          type="date"
          value={filtros.date_from ?? ''}
          onChange={(evento) => actualizar({ date_from: evento.target.value })}
        />
        <FormField
          id="filtro-hasta"
          label="Hasta"
          type="date"
          value={filtros.date_to ?? ''}
          onChange={(evento) => actualizar({ date_to: evento.target.value })}
        />
        <SelectField
          id="filtro-tipo"
          label="Tipo"
          value={filtros.type ?? ''}
          onChange={(evento) =>
            actualizar({ type: (evento.target.value || undefined) as TransactionType })
          }
        >
          <option value="">Todos</option>
          <option value="EXPENSE">Gastos</option>
          <option value="INCOME">Ingresos</option>
        </SelectField>
        <SelectField
          id="filtro-categoria"
          label="Categoría"
          value={filtros.category_id ?? ''}
          onChange={(evento) =>
            actualizar({
              category_id: evento.target.value === '' ? undefined : Number(evento.target.value),
            })
          }
        >
          <option value="">Todas</option>
          {(categorias.data ?? []).map((categoria) => (
            <option key={categoria.id} value={categoria.id}>
              {categoria.name}
            </option>
          ))}
        </SelectField>
        <FormField
          id="filtro-texto"
          label="Buscar"
          type="search"
          placeholder="En la descripción"
          value={filtros.q ?? ''}
          onChange={(evento) => actualizar({ q: evento.target.value })}
        />
      </div>

      {hayFiltros && (
        <button
          type="button"
          className="boton boton--secundario boton--chico"
          onClick={() => onCambiar(FILTROS_VACIOS)}
        >
          Limpiar filtros
        </button>
      )}
    </section>
  )
}
