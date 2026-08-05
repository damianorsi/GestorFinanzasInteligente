import { useState } from 'react'

import { ConfirmDialog } from '@/components/ConfirmDialog'
import { Cargando, ErrorVisible, SinDatos } from '@/components/Feedback'
import { Modal } from '@/components/Modal'
import { CategoryForm } from '@/features/categories/CategoryForm'
import { useBorrarCategoria, useCategorias } from '@/features/categories/api'
import type { Category } from '@/types/api'
import { aErroresDeFormulario } from '@/utils/apiErrors'

export function CategoriesPage() {
  const categorias = useCategorias()
  const borrar = useBorrarCategoria()

  const [enFormulario, setEnFormulario] = useState<Category | 'nueva' | null>(null)
  const [aBorrar, setABorrar] = useState<Category | null>(null)
  const [errorAlBorrar, setErrorAlBorrar] = useState<string | null>(null)

  const confirmarBorrado = async () => {
    if (!aBorrar) return
    setErrorAlBorrar(null)
    try {
      await borrar.mutateAsync(aBorrar.id)
      setABorrar(null)
    } catch (excepcion) {
      // El 409 del backend enumera qué está bloqueando el borrado; se muestra
      // tal cual porque ya viene accionable.
      setErrorAlBorrar(aErroresDeFormulario(excepcion).general)
    }
  }

  const porTipo = (tipo: Category['type']) =>
    (categorias.data ?? []).filter((categoria) => categoria.type === tipo)

  return (
    <section className="pagina">
      <div className="pagina__encabezado">
        <h1>Categorías</h1>
        <button
          type="button"
          className="boton boton--primario"
          onClick={() => setEnFormulario('nueva')}
        >
          Nueva categoría
        </button>
      </div>

      {categorias.isPending && <Cargando mensaje="Cargando categorías…" />}

      {categorias.isError && (
        <ErrorVisible
          mensaje="No se pudieron cargar las categorías."
          onReintentar={() => void categorias.refetch()}
        />
      )}

      {categorias.isSuccess && categorias.data.length === 0 && (
        <SinDatos titulo="Todavía no tenés categorías" />
      )}

      {categorias.isSuccess &&
        categorias.data.length > 0 &&
        (['INCOME', 'EXPENSE'] as const).map((tipo) => (
          <div key={tipo} className="grupo">
            <h2>{tipo === 'INCOME' ? 'Ingresos' : 'Gastos'}</h2>
            <ul className="lista">
              {porTipo(tipo).map((categoria) => (
                <li key={categoria.id} className="lista__item">
                  <span
                    className="punto"
                    style={{ background: categoria.color ?? 'transparent' }}
                    aria-hidden="true"
                  />
                  <span className="lista__nombre">{categoria.name}</span>
                  {categoria.is_default && (
                    <span className="etiqueta">por defecto</span>
                  )}
                  <span className="lista__acciones">
                    <button
                      type="button"
                      className="boton boton--secundario boton--chico"
                      onClick={() => setEnFormulario(categoria)}
                    >
                      Editar
                    </button>
                    <button
                      type="button"
                      className="boton boton--secundario boton--chico"
                      onClick={() => {
                        setErrorAlBorrar(null)
                        setABorrar(categoria)
                      }}
                    >
                      Borrar
                    </button>
                  </span>
                </li>
              ))}
            </ul>
          </div>
        ))}

      <Modal
        titulo={enFormulario === 'nueva' ? 'Nueva categoría' : 'Editar categoría'}
        abierto={enFormulario !== null}
        onCerrar={() => setEnFormulario(null)}
      >
        {enFormulario !== null && (
          <CategoryForm
            categoria={enFormulario === 'nueva' ? undefined : enFormulario}
            onListo={() => setEnFormulario(null)}
          />
        )}
      </Modal>

      <ConfirmDialog
        abierto={aBorrar !== null}
        titulo="Borrar categoría"
        mensaje={
          errorAlBorrar ??
          `¿Seguro que querés borrar «${aBorrar?.name ?? ''}»? Esta acción no se puede deshacer.`
        }
        enProceso={borrar.isPending}
        onConfirmar={() => void confirmarBorrado()}
        onCancelar={() => {
          setABorrar(null)
          setErrorAlBorrar(null)
        }}
      />
    </section>
  )
}
