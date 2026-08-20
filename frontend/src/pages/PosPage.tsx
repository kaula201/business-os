import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus, Minus, Trash2, ScanBarcode, Undo2, Gift, WifiOff, Printer, X, Banknote, UtensilsCrossed, Mail } from 'lucide-react'

import Modal from '../components/ui/Modal'
import { clientsApi, posApi, productsApi } from '../services/api'

const inputCls = 'w-full rounded-lg border border-brandgray-200 bg-white px-3 py-2 text-sm focus:border-primary-400 focus:outline-none focus:ring-2 focus:ring-primary-100 dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200'

interface CartItem {
  product_id: string
  name: string
  quantity: number
  unit_price: number
  discount_percent?: number
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
  const [loyaltyBalance, setLoyaltyBalance] = useState<number | null>(null)
  const [redeemPoints, setRedeemPoints] = useState('')
  const [lastReceipt, setLastReceipt] = useState<any | null>(null)
  const [giftOpen, setGiftOpen] = useState(false)
  const [giftAmount, setGiftAmount] = useState(0)
  const [giftCards, setGiftCards] = useState<any[]>([])
  const [cashOpen, setCashOpen] = useState(false)
  const [cashAmount, setCashAmount] = useState(0)
  const [cashReason, setCashReason] = useState('')
  const [xReportData, setXReportData] = useState<any | null>(null)
  const [zReports, setZReports] = useState<any[]>([])
  const [tables, setTables] = useState<any[]>([])
  const [tableOpen, setTableOpen] = useState(false)
  const [tableName, setTableName] = useState('')
  const [tableCapacity, setTableCapacity] = useState(2)
  const [splitPayments, setSplitPayments] = useState<{ method: string; amount: number; gift_card_id?: string }[]>([])
  const [splitMethod, setSplitMethod] = useState('cash')
  const [splitAmount, setSplitAmount] = useState(0)
  const [splitGiftCard, setSplitGiftCard] = useState('')
  const [orderDiscount, setOrderDiscount] = useState(0)
  const [activeCategory, setActiveCategory] = useState('all')
  const [tipAmount, setTipAmount] = useState(0)
  const [emailFor, setEmailFor] = useState<any | null>(null)
  const [emailAddress, setEmailAddress] = useState('')
  const [payMethod, setPayMethod] = useState('cash')
  const [currency, setCurrency] = useState('GEL')
  const [currencyRate, setCurrencyRate] = useState(1)

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

  const { data: offlineData } = useQuery({
    queryKey: ['pos-offline'],
    queryFn: () => posApi.listOfflineQueue().then(r => r.data.data),
  })
  const offlineItems: any[] = offlineData || []

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
      items: cart.map(i => ({
        product_id: i.product_id,
        quantity: i.quantity,
        unit_price: i.unit_price,
        ...(i.discount_percent ? { discount_percent: i.discount_percent } : {}),
      })),
      payment_method: payMethod,
      payments: splitPayments.length > 0 ? splitPayments : undefined,
      ...(orderDiscount > 0 ? { discount_amount: orderDiscount } : {}),
      ...(tipAmount > 0 ? { tip_amount: tipAmount } : {}),
      ...(currency !== 'GEL' ? { currency, currency_rate: currencyRate } : {}),
    }),
    onSuccess: (d) => {
      qc.invalidateQueries({ queryKey: ['pos-orders'] })
      qc.invalidateQueries({ queryKey: ['pos-sessions'] })
      const order = d.data.data
      if (clientId) {
        if (loyaltyPoints > 0) {
          posApi.earnLoyalty(clientId, order.id, loyaltyPoints)
        }
        if (redeemPoints && Number(redeemPoints) > 0) {
          posApi.redeemLoyalty(clientId, Number(redeemPoints))
        }
        posApi.loyaltyBalance(clientId).then(r => setLoyaltyBalance(r.data.data.points))
      }
      if (offlineMode) {
        posApi.queueOfflineOrder('local-device', {
          session_id: openSession.id,
          client_id: clientId || null,
          items: cart.map(i => ({ product_id: i.product_id, quantity: i.quantity, unit_price: i.unit_price })),
          payment_method: 'cash',
        })
          .then(() => qc.invalidateQueries({ queryKey: ['pos-offline'] }))
      }
      setLastReceipt(order)
      setCart([])
      setClientId('')
      setLoyaltyPoints(0)
      setRedeemPoints('')
    },
  })

  const redeemMut = useMutation({
    mutationFn: (points: number) => posApi.redeemLoyalty(clientId, points),
    onSuccess: (d) => { setLoyaltyBalance(d.data.data.points); setRedeemPoints('') },
  })

  const checkLoyalty = (cid: string) => {
    setClientId(cid)
    if (cid) {
      posApi.loyaltyBalance(cid).then(r => setLoyaltyBalance(r.data.data.points))
    } else {
      setLoyaltyBalance(null)
    }
  }

  const printReceipt = () => {
    if (!lastReceipt) return
    const w = window.open('', '_blank', 'width=300,height=500')
    if (!w) return
    w.document.write(`<html><head><title>${lastReceipt.order_number}</title><style>body{font-family:monospace;font-size:12px;padding:16px}hr{border:none;border-top:1px dashed #000}</style></head><body>
      <h3 style="text-align:center">Business OS</h3>
      <p style="text-align:center">${new Date().toLocaleString('ka-GE')}</p>
      <hr/>
      <p><b>${lastReceipt.order_number}</b></p>
      ${(lastReceipt.items || []).map((i: any) => `<p>${i.product_name} × ${i.quantity}<br/>${Number(i.line_total).toFixed(2)} ₾</p>`).join('')}
      <hr/>
      <p>${t('ქვეჯამი')}: ${Number(lastReceipt.subtotal || 0).toFixed(2)} ₾</p>
      <p>VAT 18%: ${Number(lastReceipt.vat_amount || 0).toFixed(2)} ₾</p>
      <p style="font-size:16px"><b>${t('სულ')}: ${Number(lastReceipt.total).toFixed(2)} ₾</b></p>
      <hr/>
      <p style="text-align:center">${t('გმადლობთ!')}</p>
      <script>window.print()</script>
    </body></html>`)
    w.document.close()
  }

  const refundMut = useMutation({
    mutationFn: ({ id, amount }: { id: string; amount: number }) => posApi.refundOrder(id, amount),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['pos-orders'] }); qc.invalidateQueries({ queryKey: ['pos-refunds'] }); setRefundFor(null) },
  })

  const registerDevice = useMutation({
    mutationFn: () => posApi.registerFiscalDevice(deviceForm),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['pos-devices'] }); setDeviceOpen(false); setDeviceForm({ name: '', device_type: 'fiscal_printer', serial_number: '' }) },
  })

  const toggleDevice = useMutation({
    mutationFn: ({ id, is_active }: { id: string; is_active: boolean }) => posApi.updateFiscalDevice(id, is_active),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['pos-devices'] }),
  })

  const syncOffline = useMutation({
    mutationFn: (id: string) => posApi.syncOfflineOrder(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['pos-offline'] }),
  })

  const issueGift = useMutation({
    mutationFn: (amount: number) => posApi.issueGiftCard(amount),
    onSuccess: (d) => {
      setGiftCards(prev => [d.data.data, ...prev])
      setGiftOpen(false)
      setGiftAmount(0)
    },
  })

  const cashInMut = useMutation({
    mutationFn: ({ amount, reason }: { amount: number; reason: string }) => posApi.cashIn(openSession.id, amount, reason || undefined),
    onSuccess: () => { setCashOpen(false); setCashAmount(0); setCashReason('') },
  })

  const cashOutMut = useMutation({
    mutationFn: ({ amount, reason }: { amount: number; reason: string }) => posApi.cashOut(openSession.id, amount, reason || undefined),
    onSuccess: () => { setCashOpen(false); setCashAmount(0); setCashReason('') },
  })

  const loadXReport = useMutation({
    mutationFn: (sessionId: string) => posApi.xReport(sessionId).then(r => r.data.data),
    onSuccess: (data) => setXReportData(data),
  })

  const closeWithZ = useMutation({
    mutationFn: (declared: number) => posApi.zReport(openSession.id, declared),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['pos-sessions'] })
      setXReportData(null)
    },
  })

  const createTableMut = useMutation({
    mutationFn: () => posApi.createTable(tableName, tableCapacity),
    onSuccess: (d) => {
      setTables(prev => [...prev, d.data.data])
      setTableOpen(false)
      setTableName('')
      setTableCapacity(2)
    },
  })

  const occupyMut = useMutation({
    mutationFn: (id: string) => posApi.occupyTable(id),
    onSuccess: () => posApi.listTables().then(r => setTables(r.data.data)),
  })

  const freeMut = useMutation({
    mutationFn: (id: string) => posApi.freeTable(id),
    onSuccess: () => posApi.listTables().then(r => setTables(r.data.data)),
  })

  const emailReceiptMut = useMutation({
    mutationFn: ({ id, email }: { id: string; email: string }) => posApi.emailReceipt(id, email),
    onSuccess: () => { setEmailFor(null); setEmailAddress('') },
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

  const categories: string[] = Array.from(new Set((products || []).map((p: any) => p.category_name || 'სხვა')))
  const filteredProducts = activeCategory === 'all'
    ? (products || [])
    : (products || []).filter((p: any) => (p.category_name || 'სხვა') === activeCategory)

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
          <button onClick={() => { setGiftOpen(true); posApi.listGiftCards().then(r => setGiftCards(r.data.data)) }}
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium bg-brandgray-100 text-brandgray-600 dark:bg-dark-100 dark:text-gray-400">
            <Gift size={15} /> {t('სასაჩუქრე ბარათები')}
          </button>
          {openSession && (
            <button onClick={() => { setCashOpen(true); setCashAmount(0); setCashReason('') }}
              className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium bg-brandgray-100 text-brandgray-600 dark:bg-dark-100 dark:text-gray-400">
              <Banknote size={15} /> {t('სალარო')}
            </button>
          )}
          <button onClick={() => { setTableOpen(true); posApi.listTables().then(r => setTables(r.data.data)) }}
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium bg-brandgray-100 text-brandgray-600 dark:bg-dark-100 dark:text-gray-400">
            <UtensilsCrossed size={15} /> {t('მაგიდები')}
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
          <div className="flex gap-1.5 flex-wrap mb-2">
            <button
              onClick={() => setActiveCategory('all')}
              className={`px-2.5 py-1 rounded-full text-xs font-medium ${activeCategory === 'all' ? 'bg-primary-600 text-white' : 'bg-brandgray-100 text-brandgray-600 hover:bg-brandgray-200 dark:bg-dark-100 dark:text-gray-400'}`}
            >
              {t('ყველა')}
            </button>
            {categories.map((c) => (
              <button
                key={c}
                onClick={() => setActiveCategory(c)}
                className={`px-2.5 py-1 rounded-full text-xs font-medium ${activeCategory === c ? 'bg-primary-600 text-white' : 'bg-brandgray-100 text-brandgray-600 hover:bg-brandgray-200 dark:bg-dark-100 dark:text-gray-400'}`}
              >
                {c}
              </button>
            ))}
          </div>
          <div className="grid grid-cols-2 gap-2 max-h-96 overflow-y-auto">
            {filteredProducts.map((p: any) => (
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
                    <input
                      type="number" min={0} max={100} placeholder="%"
                      className="mt-1 w-16 rounded border border-brandgray-200 px-1.5 py-0.5 text-xs focus:outline-none focus:ring-1 focus:ring-primary-300 dark:border-dark-50 dark:bg-dark-100"
                      value={i.discount_percent ?? ''}
                      onChange={e => setCart(prev => prev.map(x => x.product_id === i.product_id ? { ...x, discount_percent: Number(e.target.value) || undefined } : x))}
                    />
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
            <div className="flex items-center justify-between text-brandgray-500 dark:text-gray-400">
              <span>{t('შეკვეთის ფასდაკლება')}</span>
              <input
                type="number" min={0} placeholder="₾"
                className="w-20 rounded border border-brandgray-200 px-1.5 py-0.5 text-xs text-right focus:outline-none focus:ring-1 focus:ring-primary-300 dark:border-dark-50 dark:bg-dark-100"
                value={orderDiscount || ''} onChange={e => setOrderDiscount(Number(e.target.value) || 0)}
              />
            </div>
            <div className="flex justify-between text-brandgray-500 dark:text-gray-400">
              <span>VAT 18%</span><span className="font-mono">{money(vat)}</span>
            </div>
            <div className="flex items-center justify-between text-brandgray-500 dark:text-gray-400">
              <span>{t('ჩაი (tip)')}</span>
              <input
                type="number" min={0} placeholder="₾"
                className="w-20 rounded border border-brandgray-200 px-1.5 py-0.5 text-xs text-right focus:outline-none focus:ring-1 focus:ring-primary-300 dark:border-dark-50 dark:bg-dark-100"
                value={tipAmount || ''} onChange={e => setTipAmount(Number(e.target.value) || 0)}
              />
            </div>
            <div className="flex justify-between text-lg font-bold text-gray-900 dark:text-gray-100">
              <span>{t('სულ')}</span><span className="font-mono">{money(total + tipAmount)}</span>
            </div>
          </div>

          <div className="mt-3 space-y-2">
            {/* Payment method */}
            <div className="flex gap-1.5">
              {[
                { v: 'cash', l: t('ნაღდი') },
                { v: 'card', l: t('ბარათი') },
                { v: 'credit', l: t('ანგარიშზე') },
              ].map(m => (
                <button
                  key={m.v}
                  onClick={() => setPayMethod(m.v)}
                  className={`flex-1 px-2 py-1.5 rounded-lg text-xs font-medium ${payMethod === m.v ? 'bg-primary-600 text-white' : 'bg-brandgray-100 text-brandgray-600 hover:bg-brandgray-200 dark:bg-dark-100 dark:text-gray-400'}`}
                >
                  {m.l}
                </button>
              ))}
            </div>
            {/* Currency */}
            <div className="flex gap-1.5">
              <select className={`${inputCls} flex-1`} value={currency} onChange={e => setCurrency(e.target.value)}>
                <option value="GEL">GEL</option>
                <option value="USD">USD</option>
                <option value="EUR">EUR</option>
              </select>
              {currency !== 'GEL' && (
                <input
                  type="number" min={0.0001} step={0.0001} className={`${inputCls} w-28`} placeholder={t('კურსი')}
                  value={currencyRate} onChange={e => setCurrencyRate(Number(e.target.value) || 1)}
                />
              )}
            </div>
            {/* Split payment */}
            <div className="rounded-lg border border-brandgray-100 dark:border-dark-50 p-2.5 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-brandgray-600 dark:text-gray-300">{t('გაყოფილი გადახდა')}</span>
                {splitPayments.length > 0 && (
                  <button onClick={() => setSplitPayments([])} className="text-xs text-red-500 hover:text-red-600">{t('გასუფთავება')}</button>
                )}
              </div>
              <div className="flex gap-1.5">
                <select className={`${inputCls} flex-1`} value={splitMethod} onChange={e => setSplitMethod(e.target.value)}>
                  <option value="cash">{t('ნაღდი')}</option>
                  <option value="card">{t('ბარათი')}</option>
                  <option value="gift_card">{t('სასაჩუქრე ბარათი')}</option>
                </select>
                <input type="number" min={0} className={`${inputCls} w-24`} placeholder={t('თანხა')}
                  value={splitAmount || ''} onChange={e => setSplitAmount(Number(e.target.value))} />
                {splitMethod === 'gift_card' && (
                  <select className={`${inputCls} flex-1`} value={splitGiftCard} onChange={e => setSplitGiftCard(e.target.value)}>
                    <option value="">{t('აირჩიე ბარათი')}</option>
                    {(giftCards || []).filter((g: any) => g.status === 'active').map((g: any) => (
                      <option key={g.id} value={g.id}>{g.card_number} ({g.balance})</option>
                    ))}
                  </select>
                )}
                <button
                  onClick={() => {
                    if (splitAmount <= 0) return
                    setSplitPayments(prev => [...prev, { method: splitMethod, amount: splitAmount, ...(splitMethod === 'gift_card' && splitGiftCard ? { gift_card_id: splitGiftCard } : {}) }])
                    setSplitAmount(0)
                  }}
                  className="px-2.5 py-2 rounded-lg text-xs font-medium bg-primary-600 text-white hover:bg-primary-700"
                >
                  {t('დამატება')}
                </button>
              </div>
              {splitPayments.length > 0 && (
                <div className="space-y-1">
                  {splitPayments.map((p, i) => (
                    <div key={i} className="flex items-center justify-between text-xs">
                      <span className="text-brandgray-600 dark:text-gray-300">{p.method === 'gift_card' ? t('სასაჩუქრე ბარათი') : p.method === 'card' ? t('ბარათი') : t('ნაღდი')}</span>
                      <span className="font-mono font-semibold">{money(p.amount)}</span>
                      <button onClick={() => setSplitPayments(prev => prev.filter((_, j) => j !== i))} className="text-red-400 hover:text-red-600"><X size={13} /></button>
                    </div>
                  ))}
                  <div className="flex justify-between text-xs font-semibold border-t border-brandgray-100 dark:border-dark-50 pt-1">
                    <span>{t('სულ გადახდილი')}</span>
                    <span className="font-mono">{money(splitPayments.reduce((s, p) => s + p.amount, 0))}</span>
                  </div>
                </div>
              )}
            </div>
          <select className={inputCls} value={clientId} onChange={e => checkLoyalty(e.target.value)}>
              <option value="">{t('კლიენტი (არასავალდებულო)')}</option>
              {(clients || []).map((c: any) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
            {clientId && (
              <div className="space-y-2">
                <div className="flex items-center gap-2 text-sm">
                  <Gift size={15} className="text-amber-500" />
                  <span className="text-brandgray-600 dark:text-gray-300">{t('ბალანსი')}:</span>
                  <span className="font-mono font-semibold text-amber-600 dark:text-amber-400">{loyaltyBalance ?? 0}</span>
                </div>
                <div className="flex gap-2 items-center">
                  <input type="number" className={inputCls} placeholder={t('ქულების დარიცხვა')}
                    value={loyaltyPoints || ''} onChange={e => setLoyaltyPoints(Number(e.target.value))} />
                  <input type="number" className={inputCls} placeholder={t('ჩამოჭრა')}
                    value={redeemPoints} onChange={e => setRedeemPoints(e.target.value)} />
                  {redeemPoints && Number(redeemPoints) > 0 && (
                    <button onClick={() => redeemMut.mutate(Number(redeemPoints))}
                      className="px-2.5 py-2 rounded-lg text-xs font-medium bg-amber-600 text-white hover:bg-amber-700">
                      {t('ჩამოჭრა')}
                    </button>
                  )}
                </div>
              </div>
            )}
            <button onClick={() => createOrder.mutate()} disabled={createOrder.isPending || cart.length === 0 || !openSession}
              className="w-full px-4 py-3 rounded-lg bg-primary-600 text-white text-sm font-semibold hover:bg-primary-700 disabled:opacity-50">
              {t('გადახდა და ჩეკი')} — {money(total)}
            </button>
            {lastReceipt && (
              <button onClick={printReceipt}
                className="w-full px-4 py-2 rounded-lg bg-brandgray-100 text-brandgray-700 text-sm font-medium hover:bg-brandgray-200 dark:bg-dark-100 dark:text-gray-300">
                <Printer size={14} className="inline mr-1" /> {t('ბოლო ჩეკის ბეჭდვა')} — {lastReceipt.order_number}
              </button>
            )}
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
                    <button onClick={() => { setEmailFor(o); setEmailAddress('') }} className="p-1.5 rounded-md text-gray-400 hover:text-primary-600 hover:bg-primary-50 dark:hover:bg-primary-900/30" title={t('ჩეკი ელ.ფოსტით')}>
                      <Mail size={15} />
                    </button>
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
            {offlineItems.length === 0 ? (
              <p className="text-sm text-amber-700 dark:text-amber-400">{t('რიგი ცარიელია')}</p>
            ) : (
              offlineItems.map((q: any) => (
                <div key={q.id} className="flex items-center justify-between text-sm">
                  <span className="font-mono">{q.payload?.order_number || q.device_id}</span>
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
                  <div className="flex items-center gap-2">
                    {d.is_active && <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700">{t('აქტიური')}</span>}
                    <button
                      onClick={() => toggleDevice.mutate({ id: d.id, is_active: !d.is_active })}
                      className={`px-2 py-1 rounded-md text-xs font-medium ${d.is_active ? 'bg-red-50 text-red-600 hover:bg-red-100' : 'bg-emerald-50 text-emerald-700 hover:bg-emerald-100'}`}
                    >
                      {d.is_active ? t('დეაქტივაცია') : t('აქტივაცია')}
                    </button>
                  </div>
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

      {/* Gift cards modal */}
      <Modal open={giftOpen} onClose={() => setGiftOpen(false)} title={t('სასაჩუქრე ბარათები')} size="lg">
        <div className="space-y-4">
          <div className="flex gap-2">
            <input type="number" min={1} className={inputCls} placeholder={t('თანხა')}
              value={giftAmount || ''} onChange={e => setGiftAmount(Number(e.target.value))} />
            <button onClick={() => issueGift.mutate(giftAmount)} disabled={issueGift.isPending || giftAmount <= 0}
              className="px-4 py-2 rounded-lg bg-primary-600 text-white text-sm font-medium hover:bg-primary-700 disabled:opacity-50">
              {t('ბარათის გაცემა')}
            </button>
          </div>
          <div className="space-y-1.5 max-h-64 overflow-y-auto">
            {giftCards.length === 0 ? (
              <p className="text-sm text-brandgray-400 dark:text-gray-500 text-center py-6">{t('ბარათები არ არის')}</p>
            ) : (
              giftCards.map((g: any) => (
                <div key={g.id} className="flex items-center justify-between rounded-lg border border-brandgray-100 dark:border-dark-50 px-3 py-2 text-sm">
                  <div>
                    <div className="font-medium font-mono">{g.card_number}</div>
                    <div className="text-xs text-brandgray-500">PIN: {g.pin} · {g.status}</div>
                  </div>
                  <span className="font-mono font-semibold">{money(g.balance)}</span>
                </div>
              ))
            )}
          </div>
        </div>
      </Modal>

      {/* Cash register modal */}
      <Modal open={cashOpen} onClose={() => setCashOpen(false)} title={t('სალარო')} size="lg">
        {openSession && (
          <div className="space-y-4">
            <div className="flex gap-2">
              <input type="number" min={0} className={inputCls} placeholder={t('თანხა')}
                value={cashAmount || ''} onChange={e => setCashAmount(Number(e.target.value))} />
              <input className={inputCls} placeholder={t('მიზეზი')}
                value={cashReason} onChange={e => setCashReason(e.target.value)} />
              <button onClick={() => cashInMut.mutate({ amount: cashAmount, reason: cashReason })}
                disabled={cashInMut.isPending || cashAmount <= 0}
                className="px-3 py-2 rounded-lg bg-emerald-600 text-white text-sm font-medium hover:bg-emerald-700 disabled:opacity-50">
                {t('შეტანა')}
              </button>
              <button onClick={() => cashOutMut.mutate({ amount: cashAmount, reason: cashReason })}
                disabled={cashOutMut.isPending || cashAmount <= 0}
                className="px-3 py-2 rounded-lg bg-amber-600 text-white text-sm font-medium hover:bg-amber-700 disabled:opacity-50">
                {t('ამოღება')}
              </button>
            </div>
            <div className="flex gap-2">
              <button onClick={() => loadXReport.mutate(openSession.id)} disabled={loadXReport.isPending}
                className="px-4 py-2 rounded-lg bg-brandgray-100 text-brandgray-700 text-sm font-medium hover:bg-brandgray-200 dark:bg-dark-100 dark:text-gray-300">
                {t('X-ანგარიში')}
              </button>
              <button onClick={() => closeWithZ.mutate(xReportData?.expected_cash ?? 0)} disabled={closeWithZ.isPending}
                className="px-4 py-2 rounded-lg bg-red-600 text-white text-sm font-medium hover:bg-red-700">
                {t('Z-ანგარიში და დახურვა')}
              </button>
            </div>
            {xReportData && (
              <div className="rounded-lg border border-brandgray-100 dark:border-dark-50 p-4 text-sm space-y-1.5">
                <div className="flex justify-between"><span className="text-brandgray-500">{t('შეკვეთები')}</span><span className="font-semibold">{xReportData.total_orders}</span></div>
                <div className="flex justify-between"><span className="text-brandgray-500">{t('ნაღდი გაყიდვები')}</span><span className="font-mono font-semibold">{money(xReportData.cash_sales)}</span></div>
                <div className="flex justify-between"><span className="text-brandgray-500">{t('ბარათით')}</span><span className="font-mono font-semibold">{money(xReportData.card_sales)}</span></div>
                <div className="flex justify-between"><span className="text-brandgray-500">{t('დაბრუნებები')}</span><span className="font-mono font-semibold text-red-600">-{money(xReportData.total_refunds)}</span></div>
                <div className="flex justify-between"><span className="text-brandgray-500">{t('შეტანა/ამოღება')}</span><span className="font-mono">{money(xReportData.cash_in)} / {money(xReportData.cash_out)}</span></div>
                <div className="flex justify-between border-t border-brandgray-100 dark:border-dark-50 pt-2 font-bold">
                  <span>{t('მოსალოდნელი ნაღდი')}</span><span className="font-mono">{money(xReportData.expected_cash)}</span>
                </div>
              </div>
            )}
          </div>
        )}
      </Modal>

      {/* Tables modal */}
      <Modal open={tableOpen} onClose={() => setTableOpen(false)} title={t('მაგიდები')} size="lg">
        <div className="space-y-4">
          <div className="flex gap-2">
            <input className={inputCls} placeholder={t('მაგიდის სახელი')}
              value={tableName} onChange={e => setTableName(e.target.value)} />
            <input type="number" min={1} max={50} className={`${inputCls} w-24`} placeholder={t('ადგილები')}
              value={tableCapacity} onChange={e => setTableCapacity(Number(e.target.value))} />
            <button onClick={() => createTableMut.mutate()} disabled={createTableMut.isPending || !tableName}
              className="px-4 py-2 rounded-lg bg-primary-600 text-white text-sm font-medium hover:bg-primary-700 disabled:opacity-50">
              {t('დამატება')}
            </button>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 max-h-72 overflow-y-auto">
            {tables.length === 0 ? (
              <p className="text-sm text-brandgray-400 dark:text-gray-500 col-span-full text-center py-6">{t('მაგიდები არ არის')}</p>
            ) : (
              tables.map((tb: any) => (
                <div key={tb.id} className={`rounded-lg border p-3 text-sm ${tb.status === 'occupied' ? 'border-red-200 bg-red-50/60 dark:border-red-900/40 dark:bg-red-900/10' : 'border-emerald-200 bg-emerald-50/60 dark:border-emerald-900/40 dark:bg-emerald-900/10'}`}>
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-gray-900 dark:text-gray-100">{tb.name}</span>
                    <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${tb.status === 'occupied' ? 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300' : 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300'}`}>
                      {tb.status === 'occupied' ? t('დაკავებული') : t('თავისუფალი')}
                    </span>
                  </div>
                  <div className="text-xs text-brandgray-500 mt-1">{tb.capacity} {t('ადგილი')} · {tb.qr_code}</div>
                  <div className="mt-2">
                    {tb.status === 'occupied' ? (
                      <button onClick={() => freeMut.mutate(tb.id)} className="w-full px-2 py-1 rounded-md text-xs bg-amber-600 text-white hover:bg-amber-700">{t('გათავისუფლება')}</button>
                    ) : (
                      <button onClick={() => occupyMut.mutate(tb.id)} className="w-full px-2 py-1 rounded-md text-xs bg-primary-600 text-white hover:bg-primary-700">{t('დაკავება')}</button>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </Modal>

      {/* Email receipt modal */}
      <Modal open={!!emailFor} onClose={() => setEmailFor(null)} title={t('ჩეკი ელ.ფოსტით')}>
        {emailFor && (
          <div className="space-y-4">
            <p className="text-sm text-gray-600 dark:text-gray-300">
              {t('შეკვეთა')}: <span className="font-semibold">{emailFor.order_number}</span> — {money(Number(emailFor.total))}
            </p>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('ელ.ფოსტა')}</label>
              <input type="email" className={inputCls} value={emailAddress} onChange={e => setEmailAddress(e.target.value)} placeholder="client@example.com" />
            </div>
            <button
              onClick={() => emailReceiptMut.mutate({ id: emailFor.id, email: emailAddress })}
              disabled={emailReceiptMut.isPending || !emailAddress.includes('@')}
              className="w-full px-4 py-2 rounded-lg bg-primary-600 text-white text-sm font-medium hover:bg-primary-700 disabled:opacity-50"
            >
              {t('გაგზავნა')}
            </button>
          </div>
        )}
      </Modal>
    </div>
  )
}
