/**
 * Real offline POS store — IndexedDB-backed queue.
 *
 * When the network is down, orders are saved locally and the sale completes
 * offline. When the connection returns, queued orders sync automatically
 * (Odoo IoT-box style).
 */

const DB_NAME = 'bos-pos-offline'
const DB_VERSION = 2
const STORE = 'orders'
const CACHE_STORE = 'catalog'

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION)
    req.onupgradeneeded = () => {
      const db = req.result
      if (!db.objectStoreNames.contains(STORE)) {
        db.createObjectStore(STORE, { keyPath: 'local_id', autoIncrement: true })
      }
      if (!db.objectStoreNames.contains(CACHE_STORE)) {
        db.createObjectStore(CACHE_STORE, { keyPath: 'key' })
      }
    }
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error)
  })
}

// ── Offline orders ──────────────────────────────────────────────────────────

export async function saveOfflineOrder(payload: Record<string, unknown>): Promise<number> {
  const db = await openDb()
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, 'readwrite')
    const req = tx.objectStore(STORE).add({ payload, status: 'pending', created_at: new Date().toISOString() })
    req.onsuccess = () => resolve(req.result as number)
    req.onerror = () => reject(req.error)
  })
}

export async function listOfflineOrders(): Promise<any[]> {
  const db = await openDb()
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, 'readonly')
    const req = tx.objectStore(STORE).getAll()
    req.onsuccess = () => resolve(req.result as any[])
    req.onerror = () => reject(req.error)
  })
}

export async function removeOfflineOrder(localId: number): Promise<void> {
  const db = await openDb()
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, 'readwrite')
    const req = tx.objectStore(STORE).delete(localId)
    req.onsuccess = () => resolve()
    req.onerror = () => reject(req.error)
  })
}

export async function clearOfflineOrders(): Promise<void> {
  const db = await openDb()
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, 'readwrite')
    const req = tx.objectStore(STORE).clear()
    req.onsuccess = () => resolve()
    req.onerror = () => reject(req.error)
  })
}

// ── Catalog cache (cold-start offline) ──────────────────────────────────────

export async function cacheCatalog(key: string, data: unknown): Promise<void> {
  const db = await openDb()
  return new Promise((resolve, reject) => {
    const tx = db.transaction(CACHE_STORE, 'readwrite')
    const req = tx.objectStore(CACHE_STORE).put({ key, data, cached_at: new Date().toISOString() })
    req.onsuccess = () => resolve()
    req.onerror = () => reject(req.error)
  })
}

export async function getCachedCatalog<T>(key: string): Promise<T | null> {
  const db = await openDb()
  return new Promise((resolve, reject) => {
    const tx = db.transaction(CACHE_STORE, 'readonly')
    const req = tx.objectStore(CACHE_STORE).get(key)
    req.onsuccess = () => resolve((req.result as { data: T } | undefined)?.data ?? null)
    req.onerror = () => reject(req.error)
  })
}
