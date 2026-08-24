import { Component, ReactNode } from 'react'

interface Props {
  children: ReactNode
}

interface State {
  hasError: boolean
  message: string
}

/** Route-level error boundary — a page crash shows a friendly card, never a white screen. */
export default class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, message: '' }

  static getDerivedStateFromError(err: unknown): State {
    return { hasError: true, message: err instanceof Error ? err.message : String(err) }
  }

  componentDidCatch(err: unknown) {
    console.error('[ErrorBoundary]', err)
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex min-h-[60vh] items-center justify-center p-6">
          <div className="max-w-md w-full rounded-xl border border-red-200 bg-red-50 p-6 text-center dark:border-red-900/40 dark:bg-red-950/30">
            <div className="text-3xl mb-2">⚠️</div>
            <h2 className="text-lg font-semibold text-red-800 dark:text-red-300">გვერდის ჩატვირთვა ვერ მოხერხდა</h2>
            <p className="mt-2 text-sm text-red-700 dark:text-red-400">
              რაღაც არასწორად წავიდა. განაახლე გვერდი ან დაბრუნდი უკან.
            </p>
            {this.state.message && (
              <p className="mt-2 text-xs text-red-500 dark:text-red-500 break-all">{this.state.message}</p>
            )}
            <div className="mt-4 flex justify-center gap-2">
              <button
                onClick={() => window.location.reload()}
                className="rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700"
              >
                განახლება
              </button>
              <button
                onClick={() => { this.setState({ hasError: false, message: '' }); window.location.hash = '#/dashboard' }}
                className="rounded-lg border border-red-300 px-4 py-2 text-sm font-medium text-red-700 hover:bg-red-100 dark:border-red-800 dark:text-red-300 dark:hover:bg-red-900/40"
              >
                მთავარი გვერდი
              </button>
            </div>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}
