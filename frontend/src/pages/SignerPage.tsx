import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation } from '@tanstack/react-query'
import { PenLine, CheckCircle2, XCircle, Eraser } from 'lucide-react'
import { useParams } from 'react-router-dom'

import { api } from '../services/api'

export default function SignerPage() {
  const { t } = useTranslation()
  const { token } = useParams<{ token: string }>()
  const [email, setEmail] = useState('')
  const [result, setResult] = useState<{ status: string; message: string } | null>(null)
  const [error, setError] = useState('')
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const drawing = useRef(false)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return
    ctx.lineWidth = 2.5
    ctx.lineCap = 'round'
    ctx.strokeStyle = '#1e293b'
    ctx.fillStyle = '#fff'
    ctx.fillRect(0, 0, canvas.width, canvas.height)
  }, [])

  const getPos = (e: React.PointerEvent) => {
    const canvas = canvasRef.current!
    const rect = canvas.getBoundingClientRect()
    return { x: e.clientX - rect.left, y: e.clientY - rect.top }
  }

  const onDown = (e: React.PointerEvent) => {
    drawing.current = true
    const canvas = canvasRef.current!
    const ctx = canvas.getContext('2d')!
    const { x, y } = getPos(e)
    ctx.beginPath()
    ctx.moveTo(x, y)
  }
  const onMove = (e: React.PointerEvent) => {
    if (!drawing.current) return
    const canvas = canvasRef.current!
    const ctx = canvas.getContext('2d')!
    const { x, y } = getPos(e)
    ctx.lineTo(x, y)
    ctx.stroke()
  }
  const onUp = () => { drawing.current = false }

  const clearCanvas = () => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')!
    ctx.fillStyle = '#fff'
    ctx.fillRect(0, 0, canvas.width, canvas.height)
  }

  const getSignatureData = () => {
    const canvas = canvasRef.current
    return canvas ? canvas.toDataURL('image/png') : null
  }

  const sign = useMutation({
    mutationFn: (decision: 'sign' | 'decline') =>
      api.post('/signature-requests/sign', {
        token, signer_email: email, decision,
        signature_data: decision === 'sign' ? getSignatureData() : null,
      }),
    onSuccess: (r) => {
      setResult({ status: r.data.data.status, message: r.data.data.status === 'signed' ? t('დოკუმენტი ხელმოწერილია') : t('მოთხოვნა უარყოფილია') })
    },
    onError: (e: any) => {
      setError(e?.response?.data?.detail || t('შეცდომა ხელმოწერისას'))
    },
  })

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50 p-4 dark:bg-dark-300">
      <div className="w-full max-w-md rounded-2xl border bg-white p-8 shadow-sm dark:border-dark-50 dark:bg-dark-200">
        <div className="mb-6 flex items-center gap-3">
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary-50 text-primary-600 dark:bg-dark-100">
            <PenLine size={24} />
          </div>
          <div>
            <h1 className="text-xl font-bold text-brandgray-900 dark:text-gray-100">{t('ელექტრონული ხელმოწერა')}</h1>
            <p className="text-sm text-gray-500 dark:text-gray-400">{t('დოკუმენტის ხელმოწერა')}</p>
          </div>
        </div>

        {result ? (
          <div className="space-y-4 text-center">
            <div className={`mx-auto flex h-16 w-16 items-center justify-center rounded-full ${result.status === 'signed' ? 'bg-green-50 text-green-600' : 'bg-red-50 text-red-500'}`}>
              {result.status === 'signed' ? <CheckCircle2 size={32} /> : <XCircle size={32} />}
            </div>
            <p className="font-semibold text-brandgray-900 dark:text-gray-100">{result.message}</p>
          </div>
        ) : (
          <div className="space-y-4">
            <p className="text-sm text-gray-600 dark:text-gray-400">
              {t('მოწვევა მიღებულია. გთხოვთ მიუთითოთ თქვენი ელფოსტა (ის, რომელზეც მოწვევა გამოგიგზავნეთ) და მოაწეროთ ხელი დოკუმენტს.')}
            </p>
            <input
              type="email"
              className="input"
              placeholder={t('ელფოსტა')}
              value={email}
              onChange={e => setEmail(e.target.value)}
            />
            <div>
              <div className="mb-1 flex items-center justify-between">
                <span className="text-sm text-gray-500 dark:text-gray-400">{t('ხელმოწერა (დახაზეთ მაუსით/თითით)')}</span>
                <button onClick={clearCanvas} className="flex items-center gap-1 text-xs text-gray-500 hover:text-red-500">
                  <Eraser size={14} /> {t('გასუფთავება')}
                </button>
              </div>
              <canvas
                ref={canvasRef}
                width={380}
                height={140}
                className="w-full rounded-lg border border-gray-200 bg-white dark:border-dark-50"
                onPointerDown={onDown}
                onPointerMove={onMove}
                onPointerUp={onUp}
                onPointerLeave={onUp}
              />
            </div>
            {error && <p className="text-sm text-red-500">{error}</p>}
            <div className="flex gap-2 pt-2">
              <button
                onClick={() => sign.mutate('decline')}
                disabled={!email || sign.isPending}
                className="btn flex-1 border-red-200 text-red-600 hover:bg-red-50"
              >
                {t('უარყოფა')}
              </button>
              <button
                onClick={() => sign.mutate('sign')}
                disabled={!email || sign.isPending}
                className="btn btn-primary flex-1"
              >
                {t('ხელმოწერა')}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
