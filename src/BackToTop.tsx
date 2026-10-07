import { useEffect, useState } from 'react'
import { ArrowUp } from 'lucide-react'
import './BackToTop.css'

export default function BackToTop() {
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    const update = () => {
      setVisible(window.scrollY > 400 && window.location.hash !== '#risk-test')
    }
    update()
    window.addEventListener('scroll', update, { passive: true })
    window.addEventListener('hashchange', update)
    return () => {
      window.removeEventListener('scroll', update)
      window.removeEventListener('hashchange', update)
    }
  }, [])

  if (!visible) return null

  return (
    <button
      type="button"
      className="back-to-top"
      aria-label="回到顶部"
      title="回到顶部"
      onClick={() => window.scrollTo({
        top: 0,
        behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth',
      })}
    >
      <ArrowUp size={21} strokeWidth={1.8} aria-hidden="true" />
    </button>
  )
}
