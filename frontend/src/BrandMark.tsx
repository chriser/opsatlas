interface BrandMarkProps {
  className?: string;
}

export function BrandMark({ className = "" }: BrandMarkProps) {
  return (
    <span className={`brand-mark${className ? ` ${className}` : ""}`} aria-label="OpsAtlas">
      <span className="brand-mark__ops">Ops</span>
      <span className="brand-mark__atlas">Atlas</span>
    </span>
  );
}
