/** Trigger a file download from an API blob response */
export function downloadBlob(apiPromise: Promise<any>, filename: string) {
  return apiPromise.then((res: any) => {
    const blob = new Blob([res.data], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' })
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    window.URL.revokeObjectURL(url)
  }).catch((err: any) => {
    console.error('Download failed:', err)
    if (err.response?.status === 401) {
      alert('ავტორიზაცია საჭიროა')
    } else {
      alert('ექსპორტი ვერ მოხერხდა')
    }
  })
}