export function Brand({ compact = false }: { compact?: boolean }) {
  return <span className="brand-lockup">
    <svg className="brand-dots" aria-hidden="true" viewBox="0 0 24 24">
      {[4, 12, 20].flatMap((x, col) => [4, 12, 20].map((y, row) =>
        <circle key={`${col}-${row}`} cx={x} cy={y} r="1.7" fill={x === 12 && y === 12 ? 'var(--accent)' : 'currentColor'} />))}
    </svg>
    {!compact && <span className="brand-text">A2A <span>/ WORKSPACE</span></span>}
  </span>
}
