import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ShoppingCart, Plus, Trash2, CreditCard, Package, Store } from 'lucide-react'

import Modal from '../components/ui/Modal'
import FormField from '../components/ui/FormField'
import { ecommerceApi } from '../services/api'

export default function StorefrontPage() {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [tab, setTab] = useState<'store' | 'cart' | 'orders' | 'admin'>('store')
  const [cartId, setCartId] = useState<string | null>(localStorage.getItem('ecom_cart'))
  const [category, setCategory] = useState('')
  const [search, setSearch] = useState('')
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState<Record<string, any>>({})

  const { data: categories } = useQuery({ queryKey: ['ecom-cats'], queryFn: () => ecommerceApi.categories().then(r => r.data.data) })
  const { data: products } = useQuery({
    queryKey: ['ecom-products', category, search],
    queryFn: () => ecommerceApi.products({ category_id: category || undefined, search: search || undefined }).then(r => r.data.data.items),
  })
  const { data: cart } = useQuery({
    queryKey: ['ecom-cart', cartId],
    queryFn: () => (cartId ? ecommerceApi.getCart(cartId).then(r => r.data.data) : null),
    enabled: !!cartId,
  })
  const { data: orders } = useQuery({ queryKey: ['ecom-orders'], queryFn: () => ecommerceApi.orders().then(r => r.data.data) })
  const { data: adminProducts } = useQuery({ queryKey: ['ecom-admin'], queryFn: () => ecommerceApi.adminProducts().then(r => r.data.data.items) })

  const ensureCart = async () => {
    if (cartId) return cartId
    const r = await ecommerceApi.createCart()
    const id = r.data.data.id
    setCartId(id)
    localStorage.setItem('ecom_cart', id)
    return id
  }

  const addToCart = useMutation({
    mutationFn: async (productId: string) => {
      const cid = await ensureCart()
      await ecommerceApi.addItem(cid, { ecom_product_id: productId, quantity: 1 })
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['ecom-cart'] }),
  })

  const checkout = useMutation({
    mutationFn: () => ecommerceApi.checkout(cartId!, { shipping_fee: 0, payment_method: 'card' }),
    onSuccess: () => {
      localStorage.removeItem('ecom_cart')
      setCartId(null)
      qc.invalidateQueries({ queryKey: ['ecom-cart'] })
      qc.invalidateQueries({ queryKey: ['ecom-orders'] })
    },
  })

  const createProduct = useMutation({
    mutationFn: () => ecommerceApi.createProduct(form),
    onSuccess: () => { setOpen(false); setForm({}); qc.invalidateQueries({ queryKey: ['ecom-admin'] }) },
  })

  const tabs = [
    ['store', 'მაღაზია', Store],
    ['cart', 'კალათა', ShoppingCart],
    ['orders', 'შეკვეთები', Package],
    ['admin', 'მართვა', Plus],
  ] as const

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-brandgray-900 dark:text-gray-100">{t('ონლაინ მაღაზია')}</h1>
          <p className="mt-1 text-sm text-brandgray-500 dark:text-gray-400">{t('Storefront, კალათა, checkout, შეკვეთები')}</p>
        </div>
        {tab === 'admin' && (
          <button onClick={() => setOpen(true)} className="btn btn-primary flex items-center gap-2">
            <Plus size={18} /> {t('ახალი პროდუქტი')}
          </button>
        )}
      </div>

      <div className="flex gap-2 border-b dark:border-dark-50">
        {tabs.map(([key, label, Icon]) => (
          <button key={key} onClick={() => setTab(key)} className={`flex items-center gap-2 border-b-2 px-4 py-2 text-sm font-medium ${tab === key ? 'border-primary-600 text-primary-600' : 'border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400'}`}>
            <Icon size={16} /> {t(label)}
            {key === 'cart' && cart?.items?.length ? <span className="badge badge-primary">{cart.items.length}</span> : null}
          </button>
        ))}
      </div>

      {tab === 'store' && (
        <div className="space-y-4">
          <div className="flex flex-col gap-2 sm:flex-row">
            <input className="input sm:max-w-xs" placeholder={t('ძებნა')} value={search} onChange={e => setSearch(e.target.value)} />
            <select className="input sm:max-w-xs" value={category} onChange={e => setCategory(e.target.value)}>
              <option value="">{t('ყველა კატეგორია')}</option>
              {(categories || []).map((c: any) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </div>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {(products || []).map((p: any) => (
              <div key={p.id} className="rounded-xl border bg-white p-4 shadow-sm dark:border-dark-50 dark:bg-dark-200">
                <div className="flex h-32 items-center justify-center rounded-lg bg-gray-50 text-gray-300 dark:bg-dark-100">
                  <Store size={40} />
                </div>
                <h3 className="mt-3 font-semibold text-brandgray-900 dark:text-gray-100">{p.name}</h3>
                <p className="mt-1 text-lg font-bold text-primary-600">{p.price} ₾</p>
                <button onClick={() => addToCart.mutate(p.id)} className="btn btn-sm btn-primary mt-3 w-full flex items-center justify-center gap-1">
                  <ShoppingCart size={14} /> {t('კალათაში')}
                </button>
              </div>
            ))}
            {(products || []).length === 0 && (
              <div className="col-span-full rounded-xl border border-dashed p-10 text-center text-gray-500 dark:text-gray-400">
                {t('პროდუქტები არ არის')}
              </div>
            )}
          </div>
        </div>
      )}

      {tab === 'cart' && (
        <div className="rounded-xl border bg-white p-4 shadow-sm dark:border-dark-50 dark:bg-dark-200">
          {(cart?.items || []).length === 0 ? (
            <p className="p-8 text-center text-gray-500">{t('კალათა ცარიელია')}</p>
          ) : (
            <>
              <div className="space-y-2">
                {(cart?.items || []).map((i: any) => (
                  <div key={i.id} className="flex items-center justify-between rounded-lg border p-3 dark:border-dark-50">
                    <div>
                      <p className="font-medium text-brandgray-900 dark:text-gray-100">{i.ecom_product_id.slice(0, 8)}</p>
                      <p className="text-xs text-gray-500">{i.quantity} × {i.unit_price} ₾</p>
                    </div>
                    <p className="font-semibold">{(i.quantity * i.unit_price).toFixed(2)} ₾</p>
                  </div>
                ))}
              </div>
              <div className="mt-4 flex items-center justify-between border-t pt-4 dark:border-dark-50">
                <p className="font-semibold text-brandgray-900 dark:text-gray-100">{t('ჯამი')}: {cart?.subtotal} ₾</p>
                <button onClick={() => checkout.mutate()} className="btn btn-primary flex items-center gap-2">
                  <CreditCard size={16} /> {t('გადახდა')}
                </button>
              </div>
            </>
          )}
        </div>
      )}

      {tab === 'orders' && (
        <div className="overflow-hidden rounded-xl border bg-white shadow-sm dark:border-dark-50 dark:bg-dark-200">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-left text-xs text-gray-500 dark:bg-dark-100 dark:text-gray-400">
              <tr>
                <th className="px-4 py-3">{t('ნომერი')}</th>
                <th className="px-4 py-3">{t('სტატუსი')}</th>
                <th className="px-4 py-3">{t('ჯამი')}</th>
                <th className="px-4 py-3">{t('გადახდა')}</th>
              </tr>
            </thead>
            <tbody className="divide-y dark:divide-dark-50">
              {(orders || []).length === 0 ? (
                <tr><td colSpan={4} className="p-8 text-center text-gray-500">{t('შეკვეთები არ არის')}</td></tr>
              ) : (orders || []).map((o: any) => (
                <tr key={o.id} className="hover:bg-gray-50 dark:hover:bg-dark-100">
                  <td className="px-4 py-3 font-medium text-brandgray-900 dark:text-gray-100">{o.order_number}</td>
                  <td className="px-4 py-3"><span className="badge badge-warning">{o.status}</span></td>
                  <td className="px-4 py-3 font-semibold">{o.total} ₾</td>
                  <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{o.payment_method}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === 'admin' && (
        <div className="overflow-hidden rounded-xl border bg-white shadow-sm dark:border-dark-50 dark:bg-dark-200">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-left text-xs text-gray-500 dark:bg-dark-100 dark:text-gray-400">
              <tr>
                <th className="px-4 py-3">{t('სახელი')}</th>
                <th className="px-4 py-3">{t('ფასი')}</th>
                <th className="px-4 py-3">{t('გამოქვეყნებული')}</th>
              </tr>
            </thead>
            <tbody className="divide-y dark:divide-dark-50">
              {(adminProducts || []).length === 0 ? (
                <tr><td colSpan={3} className="p-8 text-center text-gray-500">{t('პროდუქტები არ არის')}</td></tr>
              ) : (adminProducts || []).map((p: any) => (
                <tr key={p.id} className="hover:bg-gray-50 dark:hover:bg-dark-100">
                  <td className="px-4 py-3 font-medium text-brandgray-900 dark:text-gray-100">{p.name}</td>
                  <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{p.price} ₾</td>
                  <td className="px-4 py-3">{p.is_published ? <span className="badge badge-success">{t('აქტიური')}</span> : <span className="badge">{t('გაჩერებული')}</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Modal open={open} onClose={() => setOpen(false)} title={t('ახალი პროდუქტი')}>
        <div className="space-y-4">
          <FormField label={t('სახელი')}><input className="input" value={form.name || ''} onChange={e => setForm({ ...form, name: e.target.value })} /></FormField>
          <FormField label={t('ფასი')}><input type="number" className="input" value={form.price || ''} onChange={e => setForm({ ...form, price: e.target.value })} /></FormField>
          <FormField label={t('Slug')}><input className="input" value={form.slug || ''} onChange={e => setForm({ ...form, slug: e.target.value })} /></FormField>
          <div className="flex justify-end gap-2 pt-2">
            <button className="btn" onClick={() => setOpen(false)}>{t('გაუქმება')}</button>
            <button className="btn btn-primary" onClick={() => createProduct.mutate()} disabled={!form.name || !form.price || !form.slug}>{t('შექმნა')}</button>
          </div>
        </div>
      </Modal>
    </div>
  )
}
