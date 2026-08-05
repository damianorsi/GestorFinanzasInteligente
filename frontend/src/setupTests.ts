import '@testing-library/jest-dom/vitest'

import { cleanup } from '@testing-library/react'
import { afterAll, afterEach, beforeAll } from 'vitest'

import { clearSession } from '@/services/session'
import { reiniciarContadores } from '@/test/handlers'
import { server } from '@/test/server'

// `onUnhandledRequest: 'error'` a propósito: un request que ningún handler
// atiende es casi siempre un endpoint que nadie recuerda haber agregado, y
// dejarlo pasar en silencio esconde el problema hasta producción.
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))

afterEach(() => {
  server.resetHandlers()
  cleanup()
  // El access token vive en un módulo, así que sobrevive entre tests si no se
  // limpia y hace que uno herede la sesión del anterior.
  clearSession()
  localStorage.clear()
  reiniciarContadores()
})

afterAll(() => server.close())
