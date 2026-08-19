// frontend/src/store/vendorAuthStore.ts
import { create } from 'zustand'

interface VendorUser {
  id: string
  supplier_id: string
  supplier_name: string
  email: string
  display_name: string
  status: string
  last_login_at: string | null
}

interface VendorAuthState {
  user: VendorUser | null
  accessToken: string | null
  isAuthenticated: boolean
  setAuth: (data: { user: VendorUser; access_token: string }) => void
  logout: () => void
}

export const useVendorAuthStore = create<VendorAuthState>((set) => ({
  user: JSON.parse(localStorage.getItem('vendor_user') || 'null'),
  accessToken: localStorage.getItem('vendor_access_token'),
  isAuthenticated: !!localStorage.getItem('vendor_access_token'),

  setAuth: (data) => {
    localStorage.setItem('vendor_user', JSON.stringify(data.user))
    localStorage.setItem('vendor_access_token', data.access_token)
    set({
      user: data.user,
      accessToken: data.access_token,
      isAuthenticated: true,
    })
  },

  logout: () => {
    localStorage.removeItem('vendor_user')
    localStorage.removeItem('vendor_access_token')
    set({ user: null, accessToken: null, isAuthenticated: false })
  },
}))
