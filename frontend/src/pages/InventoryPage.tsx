import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Archive,
  ArrowRightLeft,
  History,
  MapPin,
  Package,
  Pencil,
  Plus,
  Search,
  Star,
  Trash2,
  TrendingDown,
  TrendingUp,
  Warehouse as WarehouseIcon,
  Upload,
  Loader2,
} from 'lucide-react'

import { productsApi, purchaseCostsApi, warehousesApi, importApi } from '../services/api'
import DataTable from '../components/ui/DataTable'
import Modal from '../components/ui/Modal'
import FormField, { Select } from '../components/ui/FormField'
import ConfirmDialog from '../components/ui/ConfirmDialog'
import { StatusBadge, stockStatusMap } from '../components/ui/Badges'
import type {
  InventoryBalance,
  Product,
  ProductCreate,
  PurchaseCostHistory,
  StockTransfer,
  Warehouse,
  WarehouseCreate,
  WarehouseUpdate,
  WarehouseStockAdjustment,
} from '../types'

const emptyProduct: ProductCreate = {
  sku: '',
  name: '',
  description: '',
  category_id: '',
  barcode: '',
  sale_price: 0,
  purchase_price: undefined,
  unit: 'ცალი',
  min_stock: 0,
  current_stock: 0,
}

export default function InventoryPage() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [searchInput, setSearchInput] = useState('')
  const [page, setPage] = useState(1)
  const [productModalOpen, setProductModalOpen] = useState(false)
  const [warehouseModalOpen, setWarehouseModalOpen] = useState(false)
  const [showArchived, setShowArchived] = useState(false)
  const [editWarehouse, setEditWarehouse] = useState<Warehouse | null>(null)
  const [warehouseAction, setWarehouseAction] = useState<{
    warehouse: Warehouse
    action: 'archive' | 'delete'
  } | null>(null)
  const [transferModalOpen, setTransferModalOpen] = useState(false)
  const [editProduct, setEditProduct] = useState<Product | null>(null)
  const [stockProduct, setStockProduct] = useState<Product | null>(null)
  const [costProduct, setCostProduct] = useState<Product | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<Product | null>(null)
  const [importModal, setImportModal] = useState(false)
  const [importFile, setImportFile] = useState<File | null>(null)
  const [importResult, setImportResult] = useState('')
  const [importLoading, setImportLoading] = useState(false)
  const [formError, setFormError] = useState('')
  const [productForm, setProductForm] = useState<ProductCreate>(emptyProduct)
  const [warehouseForm, setWarehouseForm] = useState<WarehouseCreate>({
    code: '',
    name: '',
    address: '',
    is_default: false,
  })
  const [stockForm, setStockForm] = useState<WarehouseStockAdjustment>({
    product_id: '',
    warehouse_id: '',
    movement_type: 'in',
    quantity: 1,
    reason: 'purchase',
    notes: '',
  })
  const [transferForm, setTransferForm] = useState<StockTransfer>({
    product_id: '',
    source_warehouse_id: '',
    destination_warehouse_id: '',
    quantity: 1,
    reason: 'branch_replenishment',
    notes: '',
  })

  // Debounce: search იგზავნება server-ზე მხოლოდ აკრეფის შეწყვეტის შემდეგ
  useEffect(() => {
    const t = setTimeout(() => { setSearch(searchInput); setPage(1) }, 400)
    return () => clearTimeout(t)
  }, [searchInput])

  const { data, isLoading, isError: productsError } = useQuery({
    queryKey: ['products', search, page],
    queryFn: () =>
      productsApi.list({ search: search || undefined, page, page_size: 20 }).then((r) => r.data.data),
  })
  const { data: categoriesData } = useQuery({
    queryKey: ['categories'],
    queryFn: () => productsApi.listCategories().then((r) => r.data.data),
  })
  const { data: warehousesData, isLoading: warehousesLoading, isError: warehousesError } = useQuery({
    queryKey: ['warehouses', showArchived],
    queryFn: () => warehousesApi.list({ include_inactive: showArchived }).then((r) => r.data.data),
  })
  const { data: balancesData, isError: balancesError } = useQuery({
    queryKey: ['warehouse-balances'],
    queryFn: () => warehousesApi.balances().then((r) => r.data.data),
  })
  const { data: costHistoryData, isLoading: costHistoryLoading } = useQuery({
    queryKey: ['purchase-cost-history', costProduct?.id],
    queryFn: () => purchaseCostsApi.list({ product_id: costProduct!.id, page_size: 100 }).then((r) => r.data.data),
    enabled: !!costProduct,
  })

  const items: Product[] = data?.items || []
  const productsTotal = data?.total || 0
  const productsTotalPages = Math.max(1, Math.ceil(productsTotal / 20))
  const categories = categoriesData || []
  const warehouses: Warehouse[] = warehousesData || []
  const activeWarehouses = warehouses.filter((warehouse) => warehouse.is_active)
  const balances: InventoryBalance[] = balancesData || []
  const costHistory: PurchaseCostHistory[] = costHistoryData?.items || []

  const warehouseTotals = useMemo(() => {
    if (balancesError) return {}
    return balances.reduce<Record<string, number>>((totals, balance) => {
      totals[balance.warehouse_id] = (totals[balance.warehouse_id] || 0) + balance.quantity
      return totals
    }, {})
  }, [balances, balancesError])

  const refreshInventory = () => {
    queryClient.invalidateQueries({ queryKey: ['products'] })
    queryClient.invalidateQueries({ queryKey: ['warehouse-balances'] })
  }

  const createProductMutation = useMutation({
    mutationFn: (payload: ProductCreate) => productsApi.create(payload),
    onSuccess: () => {
      refreshInventory()
      closeProductModal()
    },
  })

  const createWarehouseMutation = useMutation({
    mutationFn: (payload: WarehouseCreate) => warehousesApi.create(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['warehouses'] })
      closeWarehouseModal()
    },
    onError: (error: any) => setFormError(error.response?.data?.detail || t('საწყობის შენახვა ვერ მოხერხდა')),
  })

  const updateWarehouseMutation = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: WarehouseUpdate }) => warehousesApi.update(id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['warehouses'] })
      closeWarehouseModal()
    },
    onError: (error: any) => setFormError(error.response?.data?.detail || t('საწყობის განახლება ვერ მოხერხდა')),
  })

  const setDefaultWarehouseMutation = useMutation({
    mutationFn: (id: string) => warehousesApi.setDefault(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['warehouses'] })
      setFormError('')
    },
    onError: (error: any) => setFormError(error.response?.data?.detail || t('მთავარი საწყობის შეცვლა ვერ მოხერხდა')),
  })

  const archiveWarehouseMutation = useMutation({
    mutationFn: (id: string) => warehousesApi.archive(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['warehouses'] })
      setWarehouseAction(null)
      setFormError('')
    },
    onError: (error: any) => {
      setFormError(error.response?.data?.detail || t('საწყობის დეაქტივაცია ვერ მოხერხდა'))
      setWarehouseAction(null)
    },
  })

  const deleteWarehouseMutation = useMutation({
    mutationFn: (id: string) => warehousesApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['warehouses'] })
      setWarehouseAction(null)
      setFormError('')
    },
    onError: (error: any) => {
      setFormError(error.response?.data?.detail || t('საწყობის წაშლა ვერ მოხერხდა'))
      setWarehouseAction(null)
    },
  })

  const stockMutation = useMutation({
    mutationFn: (payload: WarehouseStockAdjustment) => warehousesApi.adjustStock(payload),
    onSuccess: () => {
      refreshInventory()
      setStockProduct(null)
      setFormError('')
    },
    onError: (error: any) => setFormError(error.response?.data?.detail || t('ოპერაცია ვერ შესრულდა')),
  })

  const transferMutation = useMutation({
    mutationFn: (payload: StockTransfer) => warehousesApi.transfer(payload),
    onSuccess: () => {
      refreshInventory()
      setTransferModalOpen(false)
      setFormError('')
    },
    onError: (error: any) => setFormError(error.response?.data?.detail || t('გადატანა ვერ შესრულდა')),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => productsApi.update(id, { is_active: false }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['products'] })
      setDeleteTarget(null)
    },
  })

  function openWarehouseCreate() {
    setEditWarehouse(null)
    setWarehouseForm({ code: '', name: '', address: '', is_default: false })
    setFormError('')
    setWarehouseModalOpen(true)
  }

  function openWarehouseEdit(warehouse: Warehouse) {
    setEditWarehouse(warehouse)
    setWarehouseForm({
      code: warehouse.code,
      name: warehouse.name,
      address: warehouse.address || '',
      is_default: warehouse.is_default,
    })
    setFormError('')
    setWarehouseModalOpen(true)
  }

  function closeWarehouseModal() {
    setWarehouseModalOpen(false)
    setEditWarehouse(null)
    setWarehouseForm({ code: '', name: '', address: '', is_default: false })
    setFormError('')
  }

  function handleWarehouseSubmit(event: React.FormEvent) {
    event.preventDefault()
    if (editWarehouse) {
      updateWarehouseMutation.mutate({
        id: editWarehouse.id,
        payload: {
          code: warehouseForm.code,
          name: warehouseForm.name,
          address: warehouseForm.address,
        },
      })
      return
    }
    createWarehouseMutation.mutate(warehouseForm)
  }

  function confirmWarehouseAction() {
    if (!warehouseAction) return
    if (warehouseAction.action === 'archive') {
      archiveWarehouseMutation.mutate(warehouseAction.warehouse.id)
    } else {
      deleteWarehouseMutation.mutate(warehouseAction.warehouse.id)
    }
  }

  function openProductCreate() {
    setEditProduct(null)
    setProductForm(emptyProduct)
    setProductModalOpen(true)
  }

  function openProductEdit(product: Product) {
    setEditProduct(product)
    setProductForm({
      sku: product.sku,
      name: product.name,
      description: product.description || '',
      category_id: product.category_id || '',
      barcode: product.barcode || '',
      sale_price: product.sale_price,
      purchase_price: product.purchase_price,
      unit: product.unit,
      min_stock: product.min_stock,
      current_stock: product.current_stock,
    })
    setProductModalOpen(true)
  }

  function closeProductModal() {
    setProductModalOpen(false)
    setEditProduct(null)
  }

  function handleProductSubmit(event: React.FormEvent) {
    event.preventDefault()
    if (editProduct) {
      const updatePayload = { ...productForm }
      delete updatePayload.current_stock
      productsApi.update(editProduct.id, updatePayload).then(() => {
        refreshInventory()
        closeProductModal()
      })
      return
    }
    createProductMutation.mutate(productForm)
  }

  function openStockAdjust(product: Product) {
    const defaultWarehouse = activeWarehouses.find((warehouse) => warehouse.is_default) || activeWarehouses[0]
    setFormError('')
    setStockForm({
      product_id: product.id,
      warehouse_id: defaultWarehouse?.id || '',
      movement_type: 'in',
      quantity: 1,
      reason: 'purchase',
      notes: '',
    })
    setStockProduct(product)
  }

  function openTransfer() {
    setFormError('')
    setTransferForm({
      product_id: items[0]?.id || '',
      source_warehouse_id: activeWarehouses[0]?.id || '',
      destination_warehouse_id: activeWarehouses[1]?.id || '',
      quantity: 1,
      reason: 'branch_replenishment',
      notes: '',
    })
    setTransferModalOpen(true)
  }

  const columns = [
    {
      key: 'sku',
      label: 'SKU',
      render: (product: Product) => <span className="font-mono text-sm text-gray-500 dark:text-gray-400">{product.sku}</span>,
    },
    {
      key: 'barcode',
      label: t('შტრიხკოდი'),
      render: (product: Product) => product.barcode
        ? <span className="font-mono text-sm text-gray-500 dark:text-gray-400">{product.barcode}</span>
        : <span className="text-gray-300 dark:text-gray-600">—</span>,
    },
    {
      key: 'name',
      label: 'დასახელება',
      render: (product: Product) => <span className="font-medium text-gray-900 dark:text-gray-100">{product.name}</span>,
    },
    {
      key: 'category_name',
      label: 'კატეგორია',
      render: (product: Product) => product.category_name || '—',
      hideOnMobile: true,
    },
    {
      key: 'stock',
      label: 'ჯამური ნაშთი',
      hideOnMobile: true,
      render: (product: Product) => (
        <div className="flex items-center gap-2">
          <div className="h-2 w-24 rounded-full bg-gray-100 dark:bg-dark-100">
            <div
              className={`h-2 rounded-full ${
                product.current_stock <= product.min_stock
                  ? 'bg-red-500'
                  : product.current_stock <= product.min_stock * 2
                    ? 'bg-yellow-500'
                    : 'bg-green-500'
              }`}
              style={{ width: `${Math.min(100, (product.current_stock / (product.min_stock || 1)) * 50)}%` }}
            />
          </div>
          <span className="text-sm">{product.current_stock} / {product.min_stock}</span>
        </div>
      ),
    },
    {
      key: 'stock_status',
      label: 'სტატუსი',
      render: (product: Product) => <StatusBadge status={product.stock_status} map={stockStatusMap} />,
    },
    {
      key: 'average_cost',
      label: 'საშ. თვითღირებულება',
      render: (product: Product) => product.average_cost != null
        ? `${product.average_cost.toLocaleString('ka-GE', { minimumFractionDigits: 2, maximumFractionDigits: 4 })} ₾`
        : '—',
      className: 'font-medium text-amber-700',
      hideOnMobile: true,
    },
    {
      key: 'sale_price',
      label: 'ფასი',
      render: (product: Product) => `${product.sale_price?.toLocaleString('ka-GE')} ₾`,
      className: 'font-medium',
      hideOnMobile: true,
    },
    {
      key: 'actions',
      label: '',
      render: (product: Product) => (
        <div className="flex gap-1" onClick={(event) => event.stopPropagation()}>
          <button
            onClick={() => setCostProduct(product)}
            className="rounded p-1.5 text-gray-500 dark:text-gray-400 hover:bg-amber-50 hover:text-amber-700"
            title={t('შესყიდვის ფასების ისტორია')}
          >
            <History size={16} />
          </button>
          <button
            onClick={() => openStockAdjust(product)}
            className="rounded p-1.5 text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-dark-100 dark:bg-dark-100 hover:text-blue-600"
            title={t('საწყობის ოპერაცია')}
          >
            {product.current_stock === 0 ? <TrendingUp size={16} /> : <TrendingDown size={16} />}
          </button>
          <button onClick={() => openProductEdit(product)} title={t('რედაქტირება')} aria-label={t('რედაქტირება')} className="rounded p-1.5 text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-dark-100 dark:bg-dark-100 hover:text-primary-600"><Pencil size={16} /></button>
          <button onClick={() => setDeleteTarget(product)} title={t('წაშლა')} aria-label={t('წაშლა')} className="rounded p-1.5 text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-dark-100 dark:bg-dark-100 hover:text-red-600"><Trash2 size={16} /></button>
        </div>
      ),
    },
  ]

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">{t('საწყობი და მარაგები')}</h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">{t('მართეთ რამდენიმე საწყობი, ნაშთები და შიდა გადატანები.')}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button onClick={() => setShowArchived((value) => !value)} className="btn-secondary flex items-center gap-2">
            <Archive size={18} /> {showArchived ? t('მხოლოდ აქტიური') : t('არქივის ჩვენება')}
          </button>
          <button onClick={openWarehouseCreate} className="btn-secondary flex items-center gap-2">
            <WarehouseIcon size={18} /> {t('ახალი საწყობი')}
          </button>
          <button
            onClick={openTransfer}
            disabled={activeWarehouses.length < 2 || items.length === 0}
            className="btn-secondary flex items-center gap-2 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <ArrowRightLeft size={18} /> {t('გადატანა')}
          </button>
          <button onClick={openProductCreate} className="btn-primary flex items-center gap-2">
            <Plus size={18} /> {t('ახალი პროდუქტი')}
          </button>
          <button onClick={() => { setImportModal(true); setImportFile(null); setImportResult('') }} className="btn-secondary flex items-center gap-2">
            <Upload size={18} /> {t('Excel იმპორტი')}
          </button>
        </div>
      </div>

      {formError && !warehouseModalOpen && !stockProduct && !transferModalOpen && (
        <p className="rounded-lg border border-red-100 bg-red-50 p-3 text-sm text-red-700">{formError}</p>
      )}

      {(warehousesError || balancesError || productsError) && (
        <p className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {t('საწყობის მონაცემების ჩატვირთვა ვერ მოხერხდა. სცადეთ გვერდის განახლება.')}
        </p>
      )}

      {warehousesLoading ? (
        <div className="card p-6 text-sm text-gray-500 dark:text-gray-400">{t('საწყობების მონაცემები იტვირთება...')}</div>
      ) : warehousesError ? null : warehouses.length === 0 ? (
        <button
          onClick={openWarehouseCreate}
          className="w-full rounded-xl border-2 border-dashed border-primary-200 bg-primary-50 p-6 text-left hover:border-primary-400"
        >
          <div className="flex items-center gap-3">
            <div className="rounded-lg bg-white dark:bg-dark-200 p-3 text-primary-600"><WarehouseIcon size={24} /></div>
            <div>
              <p className="font-semibold text-gray-900 dark:text-gray-100">{t('დაამატეთ პირველი საწყობი')}</p>
              <p className="text-sm text-gray-600 dark:text-gray-400">{t('ამის შემდეგ შეძლებთ მიღებას, გაცემასა და გადატანას.')}</p>
            </div>
          </div>
        </button>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {warehouses.map((warehouse) => (
            <div key={warehouse.id} className={`card p-4 ${!warehouse.is_active ? 'border-dashed bg-gray-50 dark:bg-dark-100 opacity-75' : ''}`}>
              <div className="flex items-start justify-between gap-3">
                <div className={`rounded-lg p-2 ${warehouse.is_active ? 'bg-blue-50 text-blue-600' : 'bg-gray-100 dark:bg-dark-100 text-gray-500 dark:text-gray-400'}`}><WarehouseIcon size={20} /></div>
                <div className="flex flex-wrap justify-end gap-1">
                  {warehouse.is_default && <span className="rounded-full bg-green-50 px-2 py-1 text-xs font-medium text-green-700">{t('მთავარი')}</span>}
                  {!warehouse.is_active && <span className="rounded-full bg-gray-200 px-2 py-1 text-xs font-medium text-gray-600 dark:text-gray-400">{t('დეაქტივირებული')}</span>}
                </div>
              </div>
              <p className="mt-3 font-semibold text-gray-900 dark:text-gray-100">{warehouse.name}</p>
              <p className="text-xs font-medium text-gray-400 dark:text-gray-500">{warehouse.code}</p>
              <div className="mt-3 flex items-end justify-between">
                <span className="text-sm text-gray-500 dark:text-gray-400">{t('ჯამური ერთეული')}</span>
                <span className="text-xl font-bold text-gray-900 dark:text-gray-100">{balancesError ? '—' : (warehouseTotals[warehouse.id] || 0).toLocaleString('ka-GE')}</span>
              </div>
              {warehouse.address && <p className="mt-2 flex items-center gap-1 text-xs text-gray-500 dark:text-gray-400"><MapPin size={12} /> {warehouse.address}</p>}
              {warehouse.is_active && (
                <div className="mt-4 flex items-center justify-end gap-1 border-t border-gray-100 dark:border-dark-50 pt-3">
                  {!warehouse.is_default && (
                    <button
                      onClick={() => setDefaultWarehouseMutation.mutate(warehouse.id)}
                      className="rounded p-1.5 text-gray-500 dark:text-gray-400 hover:bg-amber-50 hover:text-amber-600"
                      title={t('მთავარ საწყობად მონიშვნა')}
                    ><Star size={16} /></button>
                  )}
                  <button onClick={() => openWarehouseEdit(warehouse)} className="rounded p-1.5 text-gray-500 dark:text-gray-400 hover:bg-blue-50 hover:text-blue-600" title={t('რედაქტირება')}><Pencil size={16} /></button>
                  {!warehouse.is_default && (
                    <>
                      <button onClick={() => setWarehouseAction({ warehouse, action: 'archive' })} className="rounded p-1.5 text-gray-500 dark:text-gray-400 hover:bg-amber-50 hover:text-amber-600" title={t('დეაქტივაცია')}><Archive size={16} /></button>
                      <button onClick={() => setWarehouseAction({ warehouse, action: 'delete' })} className="rounded p-1.5 text-gray-500 dark:text-gray-400 hover:bg-red-50 hover:text-red-600" title={t('წაშლა')}><Trash2 size={16} /></button>
                    </>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      <div className="card">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 dark:text-gray-500" size={18} />
          <input
            type="text"
            value={searchInput}
            onChange={(event) => setSearchInput(event.target.value)}
            placeholder={t('ძებნა SKU-ით ან სახელით...')}
            className="input pl-10"
          />
        </div>
      </div>

      {!productsError && (
        <DataTable columns={columns} data={items} isLoading={isLoading} emptyMessage={t('პროდუქტები არ მოიძებნა')} onRowClick={setCostProduct} page={page} totalPages={productsTotalPages} total={productsTotal} onPageChange={setPage} />
      )}

      <Modal open={!!costProduct} onClose={() => setCostProduct(null)} title={`შესყიდვის ფასების ისტორია — ${costProduct?.name || ''}`} size="xl">
        <div className="space-y-5">
          <div className="grid gap-3 sm:grid-cols-3">
            <div className="rounded-xl border border-amber-100 bg-amber-50 p-4">
              <p className="text-xs font-medium text-amber-700">{t('საშუალო თვითღირებულება')}</p>
              <p className="mt-1 text-2xl font-bold text-amber-900">
                {(costProduct?.average_cost ?? costProduct?.purchase_price ?? 0).toLocaleString('ka-GE', { minimumFractionDigits: 2, maximumFractionDigits: 4 })} ₾
              </p>
            </div>
            <div className="rounded-xl border border-blue-100 bg-blue-50 p-4">
              <p className="text-xs font-medium text-blue-700">{t('მიმდინარე ნაშთი')}</p>
              <p className="mt-1 text-2xl font-bold text-blue-900">{costProduct?.current_stock.toLocaleString('ka-GE')} {costProduct?.unit}</p>
            </div>
            <div className="rounded-xl border border-green-100 bg-green-50 p-4">
              <p className="text-xs font-medium text-green-700">{t('მარაგის ღირებულება')}</p>
              <p className="mt-1 text-2xl font-bold text-green-900">
                {((costProduct?.current_stock || 0) * (costProduct?.average_cost ?? costProduct?.purchase_price ?? 0)).toLocaleString('ka-GE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ₾
              </p>
            </div>
          </div>

          {costHistoryLoading ? (
            <p className="py-10 text-center text-sm text-gray-500 dark:text-gray-400">{t('ისტორია იტვირთება...')}</p>
          ) : costHistory.length === 0 ? (
            <div className="rounded-xl border border-dashed border-gray-200 dark:border-dark-50 py-10 text-center">
              <History className="mx-auto text-gray-300 dark:text-gray-400" size={28} />
              <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">{t('Goods Receipt-ით მიღების ისტორია ჯერ არ არსებობს.')}</p>
              <p className="mt-1 text-xs text-gray-400 dark:text-gray-500">{t('ხელით მითითებული purchase price საწყის average cost-ად გამოიყენება.')}</p>
            </div>
          ) : (
            <div className="overflow-x-auto rounded-xl border border-gray-200 dark:border-dark-50">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 dark:bg-dark-100 text-left text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">
                  <tr>
                    <th className="px-4 py-3">{t('თარიღი / დოკუმენტი')}</th>
                    <th className="px-4 py-3">{t('მომწოდებელი')}</th>
                    <th className="px-4 py-3 text-right">{t('რაოდენობა')}</th>
                    <th className="px-4 py-3 text-right">{t('ღირებულება ერთეულზე')}</th>
                    <th className="px-4 py-3 text-right">{t('ნაშთი')}</th>
                    <th className="px-4 py-3 text-right">{t('საშუალო ცვლილება')}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100 dark:divide-dark-50">
                  {costHistory.map((entry) => (
                    <tr key={entry.id} className="hover:bg-gray-50 dark:hover:bg-dark-100 dark:bg-dark-100">
                      <td className="px-4 py-3">
                        <p className="font-medium text-gray-900 dark:text-gray-100">{entry.receipt_number}</p>
                        <p className="text-xs text-gray-500 dark:text-gray-400">{entry.purchase_order_number} · {new Date(entry.created_at).toLocaleDateString('ka-GE')}</p>
                      </td>
                      <td className="px-4 py-3 text-gray-700 dark:text-gray-300">{entry.supplier_name}</td>
                      <td className="px-4 py-3 text-right font-medium">+{entry.quantity.toLocaleString('ka-GE')}</td>
                      <td className="px-4 py-3 text-right">{entry.unit_cost.toLocaleString('ka-GE', { minimumFractionDigits: 2, maximumFractionDigits: 4 })} ₾</td>
                      <td className="px-4 py-3 text-right text-gray-600 dark:text-gray-400">{entry.previous_stock.toLocaleString('ka-GE')} → {entry.new_stock.toLocaleString('ka-GE')}</td>
                      <td className="px-4 py-3 text-right">
                        <span className="text-gray-500 dark:text-gray-400">{entry.previous_average_cost.toLocaleString('ka-GE', { minimumFractionDigits: 2, maximumFractionDigits: 4 })}</span>
                        <span className="mx-1 text-gray-300 dark:text-gray-400">→</span>
                        <span className="font-semibold text-amber-700">{entry.new_average_cost.toLocaleString('ka-GE', { minimumFractionDigits: 2, maximumFractionDigits: 4 })} ₾</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <div className="flex justify-end border-t border-gray-200 dark:border-dark-50 pt-4">
            <button type="button" onClick={() => setCostProduct(null)} className="btn-secondary">{t('დახურვა')}</button>
          </div>
        </div>
      </Modal>

      <Modal open={productModalOpen} onClose={closeProductModal} title={editProduct ? t('პროდუქტის რედაქტირება') : t('ახალი პროდუქტი')} size="lg">
        <form onSubmit={handleProductSubmit} className="space-y-4">
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <FormField label="SKU" required><input value={productForm.sku} onChange={(e) => setProductForm({ ...productForm, sku: e.target.value })} className="input" required disabled={!!editProduct} /></FormField>
            <FormField label={t('შტრიხკოდი (Barcode)')}><input value={productForm.barcode || ''} onChange={(e) => setProductForm({ ...productForm, barcode: e.target.value })} className="input" placeholder="4801234567890" /></FormField>
            <FormField label={t('დასახელება')} required><input value={productForm.name} onChange={(e) => setProductForm({ ...productForm, name: e.target.value })} className="input" required /></FormField>
            <FormField label={t('კატეგორია')}><Select value={productForm.category_id || ''} onChange={(e) => setProductForm({ ...productForm, category_id: e.target.value })} placeholder={t('აირჩიეთ კატეგორია')} options={categories.map((category: any) => ({ value: category.id, label: category.name }))} /></FormField>
            <FormField label={t('ერთეული')}><Select options={[{ value: 'ცალი', label: 'ცალი' }, { value: 'კგ', label: 'კილოგრამი' }, { value: 'ლ', label: 'ლიტრი' }, { value: 'მ²', label: 'კვ. მეტრი' }, { value: 'მ', label: 'მეტრი' }]} value={productForm.unit} onChange={(e) => setProductForm({ ...productForm, unit: e.target.value })} /></FormField>
            <FormField label={t('გასაყიდი ფასი')} required><input type="number" value={productForm.sale_price || ''} onChange={(e) => setProductForm({ ...productForm, sale_price: Number(e.target.value) })} className="input" min={0} step="0.01" required /></FormField>
            <FormField label={t('შესყიდვის ფასი')}><input type="number" value={productForm.purchase_price || ''} onChange={(e) => setProductForm({ ...productForm, purchase_price: e.target.value ? Number(e.target.value) : undefined })} className="input" min={0} step="0.01" /></FormField>
            <FormField label={t('მინიმალური ნაშთი')}><input type="number" value={productForm.min_stock} onChange={(e) => setProductForm({ ...productForm, min_stock: Number(e.target.value) })} className="input" min={0} step="0.01" /></FormField>
            {!editProduct && <FormField label={t('საწყისი ჯამური ნაშთი')}><input type="number" value={productForm.current_stock} onChange={(e) => setProductForm({ ...productForm, current_stock: Number(e.target.value) })} className="input" min={0} step="0.01" /></FormField>}
          </div>
          <FormField label={t('აღწერა')}><textarea value={productForm.description || ''} onChange={(e) => setProductForm({ ...productForm, description: e.target.value })} className="input" rows={2} /></FormField>
          <div className="flex justify-end gap-3 border-t border-gray-200 dark:border-dark-50 pt-4"><button type="button" onClick={closeProductModal} className="btn-secondary">{t('გაუქმება')}</button><button type="submit" className="btn-primary">{editProduct ? t('განახლება') : t('დამატება')}</button></div>
        </form>
      </Modal>

      <Modal open={warehouseModalOpen} onClose={closeWarehouseModal} title={editWarehouse ? t('საწყობის რედაქტირება') : t('ახალი საწყობი')} size="md">
        <form onSubmit={handleWarehouseSubmit} className="space-y-4">
          <FormField label={t('კოდი')} required><input value={warehouseForm.code} onChange={(e) => setWarehouseForm({ ...warehouseForm, code: e.target.value.toUpperCase() })} className="input" placeholder="MAIN" required /></FormField>
          <FormField label={t('დასახელება')} required><input value={warehouseForm.name} onChange={(e) => setWarehouseForm({ ...warehouseForm, name: e.target.value })} className="input" placeholder={t('მთავარი საწყობი')} required /></FormField>
          <FormField label={t('მისამართი')}><input value={warehouseForm.address || ''} onChange={(e) => setWarehouseForm({ ...warehouseForm, address: e.target.value })} className="input" /></FormField>
          {!editWarehouse && <label className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300"><input type="checkbox" checked={warehouseForm.is_default || false} onChange={(e) => setWarehouseForm({ ...warehouseForm, is_default: e.target.checked })} /> {t('მთავარი საწყობი')}</label>}
          {formError && <p className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{formError}</p>}
          <div className="flex justify-end gap-3 border-t border-gray-200 dark:border-dark-50 pt-4"><button type="button" onClick={closeWarehouseModal} className="btn-secondary">{t('გაუქმება')}</button><button type="submit" className="btn-primary" disabled={createWarehouseMutation.isPending || updateWarehouseMutation.isPending}>{editWarehouse ? t('განახლება') : t('შენახვა')}</button></div>
        </form>
      </Modal>

      <Modal open={!!stockProduct} onClose={() => setStockProduct(null)} title={`საწყობის ოპერაცია — ${stockProduct?.name || ''}`} size="md">
        <form onSubmit={(event) => { event.preventDefault(); stockMutation.mutate(stockForm) }} className="space-y-4">
          <div className="flex items-center gap-3 rounded-lg bg-gray-50 dark:bg-dark-100 p-3"><Package size={20} className="text-gray-400 dark:text-gray-500" /><div><p className="text-xs text-gray-500 dark:text-gray-400">{t('ჯამური ნაშთი')}</p><p className="text-lg font-bold">{stockProduct?.current_stock || 0}</p></div></div>
          <FormField label={t('საწყობი')} required><Select value={stockForm.warehouse_id} onChange={(e) => setStockForm({ ...stockForm, warehouse_id: e.target.value })} placeholder={t('აირჩიეთ საწყობი')} options={activeWarehouses.map((warehouse) => ({ value: warehouse.id, label: `${warehouse.name} (${warehouse.code})` }))} /></FormField>
          <FormField label={t('ოპერაცია')} required><Select value={stockForm.movement_type} onChange={(e) => setStockForm({ ...stockForm, movement_type: e.target.value as WarehouseStockAdjustment['movement_type'] })} options={[{ value: 'in', label: 'მიღება' }, { value: 'out', label: 'გაცემა' }, { value: 'adjustment', label: 'ინვენტარიზაციის კორექტირება' }]} /></FormField>
          <FormField label={t('რაოდენობა')} required><input type="number" value={stockForm.quantity} onChange={(e) => setStockForm({ ...stockForm, quantity: Number(e.target.value) })} className="input" min={0} step="0.001" required /></FormField>
          <FormField label={t('მიზეზი')} required><Select value={stockForm.reason} onChange={(e) => setStockForm({ ...stockForm, reason: e.target.value })} options={[{ value: 'purchase', label: 'შესყიდვა' }, { value: 'sale', label: 'გაყიდვა' }, { value: 'inventory', label: 'ინვენტარიზაცია' }, { value: 'return', label: 'დაბრუნება' }, { value: 'loss', label: 'დანაკარგი' }, { value: 'other', label: 'სხვა' }]} /></FormField>
          <FormField label={t('შენიშვნა')}><input value={stockForm.notes || ''} onChange={(e) => setStockForm({ ...stockForm, notes: e.target.value })} className="input" /></FormField>
          {formError && <p className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{formError}</p>}
          <div className="flex justify-end gap-3 border-t border-gray-200 dark:border-dark-50 pt-4"><button type="button" onClick={() => setStockProduct(null)} className="btn-secondary">{t('გაუქმება')}</button><button type="submit" className="btn-primary" disabled={!stockForm.warehouse_id || stockMutation.isPending}>{t('შენახვა')}</button></div>
        </form>
      </Modal>

      <Modal open={transferModalOpen} onClose={() => setTransferModalOpen(false)} title={t('საწყობებს შორის გადატანა')} size="md">
        <form onSubmit={(event) => { event.preventDefault(); transferMutation.mutate(transferForm) }} className="space-y-4">
          <FormField label={t('პროდუქტი')} required><Select value={transferForm.product_id} onChange={(e) => setTransferForm({ ...transferForm, product_id: e.target.value })} placeholder={t('აირჩიეთ პროდუქტი')} options={items.map((product) => ({ value: product.id, label: `${product.name} (${product.sku})` }))} /></FormField>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <FormField label={t('საწყისი საწყობი')} required><Select value={transferForm.source_warehouse_id} onChange={(e) => setTransferForm({ ...transferForm, source_warehouse_id: e.target.value })} options={activeWarehouses.map((warehouse) => ({ value: warehouse.id, label: warehouse.name }))} /></FormField>
            <FormField label={t('დანიშნულების საწყობი')} required><Select value={transferForm.destination_warehouse_id} onChange={(e) => setTransferForm({ ...transferForm, destination_warehouse_id: e.target.value })} options={activeWarehouses.map((warehouse) => ({ value: warehouse.id, label: warehouse.name }))} /></FormField>
          </div>
          <FormField label={t('რაოდენობა')} required><input type="number" value={transferForm.quantity} onChange={(e) => setTransferForm({ ...transferForm, quantity: Number(e.target.value) })} className="input" min={0.001} step="0.001" required /></FormField>
          <FormField label={t('მიზეზი')} required><input value={transferForm.reason} onChange={(e) => setTransferForm({ ...transferForm, reason: e.target.value })} className="input" required /></FormField>
          <FormField label={t('შენიშვნა')}><input value={transferForm.notes || ''} onChange={(e) => setTransferForm({ ...transferForm, notes: e.target.value })} className="input" /></FormField>
          {formError && <p className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{formError}</p>}
          <div className="flex justify-end gap-3 border-t border-gray-200 dark:border-dark-50 pt-4"><button type="button" onClick={() => setTransferModalOpen(false)} className="btn-secondary">{t('გაუქმება')}</button><button type="submit" className="btn-primary" disabled={transferMutation.isPending}>{t('გადატანა')}</button></div>
        </form>
      </Modal>

      <ConfirmDialog open={!!deleteTarget} onClose={() => setDeleteTarget(null)} onConfirm={() => deleteTarget && deleteMutation.mutate(deleteTarget.id)} title={t('პროდუქტის დეაქტივაცია')} message={`დარწმუნებული ხართ, რომ გსურთ „${deleteTarget?.name}“-ის დეაქტივაცია?`} confirmLabel="დეაქტივაცია" loading={deleteMutation.isPending} />
      <ConfirmDialog
        open={!!warehouseAction}
        onClose={() => setWarehouseAction(null)}
        onConfirm={confirmWarehouseAction}
        title={warehouseAction?.action === 'delete' ? t('საწყობის წაშლა') : t('საწყობის დეაქტივაცია')}
        message={warehouseAction?.action === 'delete'
          ? `„${warehouseAction?.warehouse.name}“ სრულად წაიშლება მხოლოდ მაშინ, თუ არასოდეს გამოუყენებიათ.`
          : `„${warehouseAction?.warehouse.name}“ ახალ ოპერაციებში აღარ გამოჩნდება, ხოლო ისტორია შენარჩუნდება. ნაშთი განულებული უნდა იყოს.`}
        confirmLabel={warehouseAction?.action === 'delete' ? t('წაშლა') : t('დეაქტივაცია')}
        variant={warehouseAction?.action === 'delete' ? 'danger' : 'warning'}
        loading={archiveWarehouseMutation.isPending || deleteWarehouseMutation.isPending}
      />

      {/* Import Modal */}
      <Modal open={importModal} onClose={() => setImportModal(false)} title={t('პროდუქტების Excel იმპორტი')} size="md">
        {importResult ? (
          <div className="text-center py-4">
            <p className="text-sm text-gray-700 dark:text-gray-300 whitespace-pre-line">{importResult}</p>
            <button onClick={() => { setImportModal(false); queryClient.invalidateQueries({ queryKey: ['products'] }) }} className="btn-primary mt-6">{t('დახურვა')}</button>
          </div>
        ) : (
          <div className="space-y-4">
            <p className="text-sm text-gray-600 dark:text-gray-400">
              {t('ატვირთეთ Excel ფაილი (.xlsx) პროდუქტების სიით. მოსალოდნელი სვეტები:')}
              <code className="block mt-2 text-xs bg-gray-100 dark:bg-dark-100 p-2 rounded">sku, name, category, unit, sale_price, purchase_price, min_stock, current_stock</code>
            </p>
            <input
              type="file"
              accept=".xlsx,.xls"
              onChange={(e) => setImportFile(e.target.files?.[0] || null)}
              className="block w-full text-sm text-gray-500 dark:text-gray-400 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-primary-50 file:text-primary-700 hover:file:bg-primary-100"
            />
            {importFile && <p className="text-xs text-gray-400 dark:text-gray-500">არჩეულია: {importFile.name}</p>}
            <div className="flex justify-end gap-3 pt-2">
              <button onClick={() => setImportModal(false)} className="btn-secondary">{t('გაუქმება')}</button>
              <button
                onClick={async () => {
                  if (!importFile) return
                  setImportLoading(true)
                  setImportResult('')
                  try {
                    const res = await importApi.importProducts(importFile)
                    setImportResult(res.data.data?.message || t('იმპორტი დასრულდა'))
                  } catch (err: any) {
                    setImportResult(err?.response?.data?.detail || t('შეცდომა იმპორტის დროს'))
                  } finally {
                    setImportLoading(false)
                  }
                }}
                disabled={!importFile || importLoading}
                className="btn-primary"
              >
                {importLoading ? <><Loader2 size={16} className="animate-spin" /> {t('იტვირთება...')}</> : 'ატვირთვა'}
              </button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  )
}
