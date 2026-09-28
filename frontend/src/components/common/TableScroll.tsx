import { type ReactNode, useEffect, useRef, useState } from 'react'

interface TableScrollProps {
  /** Names the scroll box for screen readers: the table's caption. */
  label: string
  className?: string
  children: ReactNode
}

/**
 * A wide table's own horizontal scroll box, so the page itself never scrolls sideways on a
 * phone (e2e/mobile.spec.ts checks every page at 375px). While the table is wider than the
 * box, the box is a focusable, labelled region, so it can be scrolled from the keyboard too;
 * when everything fits, it's an ordinary div and adds no tab stop.
 */
export function TableScroll({ label, className, children }: TableScrollProps) {
  const ref = useRef<HTMLDivElement>(null)
  const [overflowing, setOverflowing] = useState(false)

  useEffect(() => {
    const box = ref.current
    if (!box || typeof ResizeObserver === 'undefined') return
    const check = () => setOverflowing(box.scrollWidth > box.clientWidth + 1)
    const observer = new ResizeObserver(check)
    observer.observe(box)
    if (box.firstElementChild) observer.observe(box.firstElementChild)
    check()
    return () => observer.disconnect()
  }, [])

  return (
    <div
      ref={ref}
      className={className}
      {...(overflowing ? { role: 'region', 'aria-label': label, tabIndex: 0 } : {})}
    >
      {children}
    </div>
  )
}
