import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus, Minus, Trash2, ScanBarcode, Undo2, Gift, WifiOff, Printer, X } from 'lucide-react'

import Modal from '../components/ui/Modal'
import { clientsApi, posApi, productsApi } from '../services/api'

const inputCls = 'w-full rounded-lg border border-brandgray-200 bg-white px-3 py-2 text-sm focus:border-primary-400 focus:outline-none focus:ring-2 focus:ring-primary-100 dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200'

interface CartItem {
  product_id: string
  name: string
  quantity: number
  unit_price: number
  line_total: number
}

export default function PosPage() {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [sessionOpen, setSessionOpen] = useState(false)
  const [sessionName, setSessionName] = useState('')
  const [cart, setCart] = useState<CartItem[]>([])
  const [barcode, setBarcode] = useState('')
  const [clientId, setClientId] = useState('')
  const [loyaltyPoints, setLoyaltyPoints] = useState(0)
  const [refundFor, setRefundFor] = useState<any | null>(null)
  const [deviceOpen, setDeviceOpen] = useState(false)
  const [deviceForm, setDeviceForm] = useState({ name: '', device_type: 'fiscal_printer', serial_number: '' })
  const [offlineMode, setOfflineMode] = useState(false)
  const [offlineQueue, setOfflineQueue] = useState<any[]>([])

  const { data: sessionsData } = useQuery({
    queryKey: ['pos-sessions'],
    queryFn: () => posApi.listSessions().then(r => r.data.data),
  })
  const sessions: any[] = sessionsData || []
  const openSession = sessions.find((s: any) => s.status === 'open')

  const { data: ordersData } = useQuery({
    queryKey: ['pos-orders'],
    queryFn: () => posApi.listOrders().then(r => r.data.data),
  })
  const orders: any[] = ordersData || []

  const { data: refundsData } = useQuery({
    queryKey: ['pos-refunds'],
    queryFn: () => posApi.listRefunds().then(r => r.data.data),
  })
  const refunds: any[] = refundsData || []

  const { data: devicesData } = useQuery({
    queryKey: ['pos-devices'],
    queryFn: () => posApi.listFiscalDevices().then(r => r.data.data),
  })
  const devices: any[] = devicesData || []

  const { data: products } = useQuery({
    queryKey: ['products-all-pos'],
    queryFn: () => productsApi.list({ page_size: 200 }).then(r => r.data.data.items),
  })
  const { data: clients } = useQuery({
    queryKey: ['clients-all-pos'],
    queryFn: () => clientsApi.list({ page_size: 200 }).then(r => r.data.data.items),
  })

  const openSessionMut = useMutation({
    mutationFn: () => posApi.openSession({ name: sessionName }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['pos-sessions'] }); setSessionOpen(false); setSessionName('') },
  })

  const closeSessionMut = useMutation({
    mutationFn: (id: string) => posApi.closeSession(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['pos-sessions'] }),
  })

  const createOrder = useMutation({
    mutationFn: () => posApi.createOrder({
      session_id: openSession.id,
      client_id: clientId || null,
      items: cart.map(i => ({ product_id: i.product_id, quantity: i.quantity, unit_price: i.unit_price })),
      payment_method: 'cash',
    }),
    onSuccess: (d) => {
      qc.invalidateQueries({ queryKey: ['pos-orders'] })
      qc.invalidateQueries({ queryKey: ['pos-sessions'] })
      if (clientId && loyaltyPoints > 0) {
        posApi.earnLoyalty(clientId, d.data.data.id, loyaltyPoints)
      }
      setCart([])
      setClientId('')
      setLoyaltyPoints(0)
    },
  })

  const refundMut = useMutation({
    mutationFn: ({ id, amount }: { id: string; amount: number }) => posApi.refundOrder(id, amount),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['pos-orders'] }); qc.invalidateQueries({ queryKey: ['pos-refunds'] }); setRefundFor(null) },
  })

  const registerDevice = useMutation({
    mutationFn: () => posApi.registerFiscalDevice(deviceForm),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['pos-devices'] }); setDeviceOpen(false); setDeviceForm({ name: '', device_type: 'fiscal_printer', serial_number: '' }) },
  })

  const syncOffline = useMutation({
    mutationFn: (id: string) => posApi.syncOfflineOrder(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['pos-offline'] }),
  })

  const addByBarcode = () => {
    const p = (products || []).find((x: any) => x.barcode === barcode || x.sku === barcode)
    if (p) {
      addToCart(p)
      setBarcode('')
    }
  }

  const addToCart = (p: any) => {
    setCart(prev => {
      const existing = prev.find(i => i.product_id === p.id)
      if (existing) {
        return prev.map(i => i.product_id === p.id ? { ...i, quantity: i.quantity + 1, line_total: (i.quantity + 1) * i.unit_price } : i)
      }
      return [...prev, { product_id: p.id, name: p.name, quantity: 1, unit_price: Number(p.sale_price), line_total: Number(p.sale_price) }]
    })
  }

  const subtotal = cart.reduce((s, i) => s + i.line_total, 0)
  const vat = subtotal * 0.18
  const total = subtotal + vat

  const money = (v: number) => new Intl.NumberFormat('ka-GE', { style: 'currency', currency: 'GEL' }).format(v)

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-brandgray-800 dark:text-gray-100">{t('სალარო (POS)')}</h1>
          <p className="text-sm text-brandgray-500 dark:text-gray-400">
            {openSession ? `${t('ღია ცვლა')}: ${openSession.name}` : t('ცვლა დახურულია')}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button onClick={() => setOfflineMode(!offlineMode)}
            className={`inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium ${offlineMode ? 'bg-amber-600 text-white' : 'bg-brandgray-100 text-brandgray-600 dark:bg-dark-100 dark:text-gray-400'}`}>
            <WifiOff size={15} /> {t('Offline')}
          </button>
          <button onClick={() => setDeviceOpen(true)}
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium bg-brandgray-100 text-brandgray-600 dark:bg-dark-100 dark:text-gray-400">
            <Printer size={15} /> {t('ფისკალური მოწყობილობები')}
          </button>
          {openSession ? (
            <button onClick={() => closeSessionMut.mutate(openSession.id)}
              className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium bg-red-600 text-white hover:bg-red-700">
              {t('ცვლის დახურვა')}
            </button>
          ) : (
            <button onClick={() => setSessionOpen(true)}
              className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium bg-primary-600 text-white hover:bg-primary-700">
              <Plus size={15} /> {t('ცვლის გახსნა')}
            </button>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        {/* Products / barcode */}
        <div className="rounded-lg border border-brandgray-100 dark:border-dark-50 p-4">
          <div className="flex gap-2 mb-3">
            <div className="relative flex-1">
              <ScanBarcode size={16} className="absolute left-3 top-2.5 text-brandgray-400" />
              <input className={`${inputCls} pl-9`} placeholder={t('Barcode ან SKU სკანირება...')}
                value={barcode} onChange={e => setBarcode(e.target.value)} onKeyDown={e => e.key === 'Enter' && addByBarcode()} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-2 max-h-96 overflow-y-auto">
            {(products || []).map((p: any) => (
              <button key={p.id} onClick={() => addToCart(p)}
                className="rounded-lg border border-brandgray-100 dark:border-dark-50 p-3 text-left hover:border-primary-300 hover:bg-primary-50/50 dark:hover:bg-primary-900/10">
                <div className="text-sm font-medium text-gray-900 dark:text-gray-100 truncate">{p.name}</div>
                <div className="text-xs text-brandgray-500 dark:text-gray-400">{p.sku}</div>
                <div className="text-sm font-semibold text-primary-700 dark:text-primary-300 mt-1">{money(Number(p.sale_price))}</div>
              </button>
            ))}
          </div>
        </div>

        {/* Cart */}
        <div className="rounded-lg border border-brandgray-100 dark:border-dark-50 p-4">
          <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">{t('მიმდინარე ჩეკი')}</h3>
          <div className="space-y-2 max-h-64 overflow-y-auto mb-3">
            {cart.length === 0 ? (
              <p className="text-sm text-brandgray-400 dark:text-gray-500 text-center py-8">{t('კალათა ცარიელია')}</p>
            ) : (
              cart.map((i, idx) => (
                <div key={idx} className="flex items-center justify-between rounded-lg bg-brandgray-50 dark:bg-dark-100 px-3 py-2 text-sm">
                  <div className="flex-1">
                    <div className="font-medium text-gray-900 dark:text-gray-100">{i.name}</div>
                    <div className="text-xs text-brandgray-500">{i.quantity} × {money(i.unit_price)}</div>
                  </div>
                  <div className="font-mono font-semibold mr-2">{money(i.line_total)}</div>
                  <div className="flex gap-1">
                    <button onClick={() => setCart(prev => prev.map(x => x.product_id === i.product_id ? { ...x, quantity: x.quantity + 1, line_total: (x.quantity + 1) * x.unit_price } : x))}
                      className="p-1 rounded text-gray-400 hover:text-primary-700"><Plus size={14} /></button>
                    <button onClick={() => setCart(prev => prev.map(x => x.product_id === i.product_id ? { ...x, quantity: Math.max(1, x.quantity - 1), line_total: Math.max(1, x.quantity - 1) * x.unit_price } : x))}
                      className="p-1 rounded text-gray-400 hover:text-amber-700"><Minus size={14} /></button>
                    <button onClick={() => setCart(prev => prev.filter(x => x.product_id !== i.product_id))}
                      className="p-1 rounded text-gray-400 hover:text-red-600"><Trash2 size={14} /></button>
                  </div>
                </div>
              ))
            )}
          </div>

          <div className="space-y-1.5 border-t border-brandgray-100 dark:border-dark-50 pt-3 text-sm">
            <div className="flex justify-between text-brandgray-500 dark:text-gray-400">
              <span>{t('ქვეჯამი')}</span><span className="font-mono">{money(subtotal)}</span>
            </div>
            <div className="flex justify-between text-brandgray-500 dark:text-gray-400">
              <span>VAT 18%</span><span className="font-mono">{money(vat)}</span>
            </div>
            <div className="flex justify-between text-lg font-bold text-gray-900 dark:text-gray-100">
              <span>{t('სულ')}</span><span className="font-mono">{money(total)}</span>
            </div>
          </div>

          <div className="mt-3 space-y-2">
            <select className={inputCls} value={clientId} onChange={e => setClientId(e.target.value)}>
              <option value="">{t('კლიენტი (არასავალდებულო)')}</option>
              {(clients || []).map((c: any) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
            {clientId && (
              <div className="flex gap-2 items-center">
                <Gift size={15} className="text-amber-500" />
                <input type="number" className={inputCls} placeholder={t('Loyalty ქულები')}
                  value={loyaltyPoints || ''} onChange={e => setLoyaltyPoints(Number(e.target.value))} />
              </div>
            )}
            <button onClick={() => createOrder.mutate()} disabled={createOrder.isPending || cart.length === 0 || !openSession}
              className="w-full px-4 py-3 rounded-lg bg-primary-600 text-white text-sm font-semibold hover:bg-primary-700 disabled:opacity-50">
              {t('გადახდა და ჩეკი')} — {money(total)}
            </button>
          </div>
        </div>
      </div>

      {/* Orders + refunds */}
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        <div className="rounded-lg border border-brandgray-100 dark:border-dark-50 p-4">
          <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">{t('შეკვეთები')}</h3>
          <div className="space-y-2 max-h-72 overflow-y-auto">
            {orders.length === 0 ? (
              <p className="text-sm text-brandgray-400 dark:text-gray-500 text-center py-6">{t('შეკვეთები არ არის')}</p>
            ) : (
              orders.map((o: any) => (
                <div key={o.id} className="flex items-center justify-between rounded-lg border border-brandgray-100 dark:border-dark-50 px-3 py-2 text-sm">
                  <div>
                    <div className="font-medium text-gray-900 dark:text-gray-100">{o.order_number}</div>
                    <div className="text-xs text-brandgray-500">{o.payment_method} · {new Date(o.created_at).toLocaleTimeString('ka-GE')}</div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="font-mono font-semibold">{money(Number(o.total))}</span>
                    {o.status !== 'refunded' && (
                      <button onClick={() => setRefundFor(o)} className="p-1.5 rounded-md text-gray-400 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-900/30" title={t('დაბრუნება')}>
                        <Undo2 size={15} />
                      </button>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        <div className="rounded-lg border border-brandgray-100 dark:border-dark-50 p-4">
          <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">{t('დაბრუნებები')}</h3>
          <div className="space-y-2 max-h-72 overflow-y-auto">
            {refunds.length === 0 ? (
              <p className="text-sm text-brandgray-400 dark:text-gray-500 text-center py-6">{t('დაბრუნებები არ არის')}</p>
            ) : (
              refunds.map((r: any) => (
                <div key={r.id} className="flex items-center justify-between rounded-lg border border-brandgray-100 dark:border-dark-50 px-3 py-2 text-sm">
                  <div>
                    <div className="font-medium text-gray-900 dark:text-gray-100">{r.refund_number}</div>
                    <div className="text-xs text-brandgray-500">{r.reason || '—'}</div>
                  </div>
                  <span className="font-mono font-semibold text-red-600 dark:text-red-400">-{money(r.amount)}</span>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {/* Offline queue */}
      {offlineMode && (
        <div className="rounded-lg border border-amber-200 dark:border-amber-900/40 bg-amber-50 dark:bg-amber-900/10 p-4">
          <h3 className="text-sm font-semibold text-amber-800 dark:text-amber-300 mb-2">{t('Offline რიგი')}</h3>
          <p className="text-xs text-amber-700 dark:text-amber-400 mb-2">{t('კავშირის აღდგენის შემდეგ შეკვეთები ავტომატურად სინქრონიზდება')}</p>
          <div className="space-y-1.5">
            {offlineQueue.length === 0 ? (
              <p className="text-sm text-amber-700 dark:text-amber-400">{t('რიგი ცარიელია')}</p>
            ) : (
              offlineQueue.map((q: any) => (
                <div key={q.id} className="flex items-center justify-between text-sm">
                  <span className="font-mono">{q.device_id}</span>
                  <span className="text-amber-700 dark:text-amber-300">{q.status}</span>
                  {q.status === 'pending' && (
                    <button onClick={() => syncOffline.mutate(q.id)} className="px-2 py-1 rounded-md text-xs bg-amber-600 text-white">{t('სინქრონიზაცია')}</button>
                  )}
                </div>
              ))
            )}
          </div>
        </div>
      )}

      <Modal open={sessionOpen} onClose={() => setSessionOpen(false)} title={t('ცვლის გახსნა')}>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('ცვლის სახელი')}</label>
            <input className={inputCls} value={sessionName} onChange={e => setSessionName(e.target.value)} placeholder="ცვლა 1" />
          </div>
          <button onClick={() => openSessionMut.mutate()} disabled={openSessionMut.isPending || !sessionName}
            className="w-full px-4 py-2 rounded-lg bg-primary-600 text-white text-sm font-medium hover:bg-primary-700 disabled:opacity-50">
            {t('გახსნა')}
          </button>
        </div>
      </Modal>

      <Modal open={!!refundFor} onClose={() => setRefundFor(null)} title={t('დაბრუნება')}>
        {refundFor && (
          <div className="space-y-4">
            <p className="text-sm text-gray-600 dark:text-gray-300">
              {t('შეკვეთა')}: <span className="font-semibold">{refundFor.order_number}</span> — {money(Number(refundFor.total))}
            </p>
            <button onClick={() => refundMut.mutate({ id: refundFor.id, amount: Number(refundFor.total) })}
              disabled={refundMut.isPending}
              className="w-full px-4 py-2 rounded-lg bg-red-600 text-white text-sm font-medium hover:bg-red-700 disabled:opacity-50">
              {t('სრული დაბრუნება')}
            </button>
          </div>
        )}
      </Modal>

      <Modal open={deviceOpen} onClose={() => setDeviceOpen(false)} title={t('ფისკალური მოწყობილობები')}>
        <div className="space-y-4">
          <div className="space-y-1.5 max-h-40 overflow-y-auto">
            {devices.length === 0 ? (
              <p className="text-sm text-brandgray-400 dark:text-gray-500">{t('მოწყობილობები არ არის')}</p>
            ) : (
              devices.map((d: any) => (
                <div key={d.id} className="flex items-center justify-between rounded-lg border border-brandgray-100 dark:border-dark-50 px-3 py-2 text-sm">
                  <div>
                    <div className="font-medium">{d.name}</div>
                    <div className="text-xs text-brandgray-500">{d.device_type} · {d.serial_number}</div>
                  </div>
                  {d.is_active && <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700">{t('აქტიური')}</span>}
                </div>
              ))
            )}
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('სახელი')}</label>
            <input className={inputCls} value={deviceForm.name} onChange={e => setDeviceForm({ ...deviceForm, name: e.target.value })} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('ტიპი')}</label>
              <select className={inputCls} value={deviceForm.device_type} onChange={e => setDeviceForm({ ...deviceForm, device_type: e.target.value })}>
                <option value="fiscal_printer">Fiscal printer</option>
                <option value="terminal">Terminal</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('სერიული ნომერი')}</label>
              <input className={inputCls} value={deviceForm.serial_number} onChange={e => setDeviceForm({ ...deviceForm, serial_number: e.target.value })} />
            </div>
          </div>
          <button onClick={() => registerDevice.mutate()} disabled={registerDevice.isPending || !deviceForm.name || !deviceForm.serial_number}
            className="w-full px-4 py-2 rounded-lg bg-primary-600 text-white text-sm font-medium hover:bg-primary-700 disabled:opacity-50">
            {t('რეგისტრაცია')}
          </button>
        </div>
      </Modal>
    </div>
  )
}
