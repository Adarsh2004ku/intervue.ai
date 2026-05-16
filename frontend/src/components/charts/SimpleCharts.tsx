type TrendPoint = {
  name: string;
  score: number;
};

type RadarPoint = {
  label: string;
  score: number;
};

const clampScore = (score: number) => Math.min(100, Math.max(0, score || 0));

export function LineTrendChart({ data }: { data: TrendPoint[] }) {
  const safeData = data.length ? data : [{ name: 'No scores yet', score: 0 }];
  const width = 640;
  const height = 260;
  const padding = { top: 24, right: 24, bottom: 48, left: 48 };
  const chartWidth = width - padding.left - padding.right;
  const chartHeight = height - padding.top - padding.bottom;
  const points = safeData.map((item, index) => {
    const x = padding.left + (safeData.length === 1 ? chartWidth / 2 : (index / (safeData.length - 1)) * chartWidth);
    const y = padding.top + (1 - clampScore(item.score) / 100) * chartHeight;
    return { ...item, x, y };
  });
  const path = points.map((point, index) => `${index === 0 ? 'M' : 'L'} ${point.x} ${point.y}`).join(' ');
  const areaPath = `${path} L ${points[points.length - 1].x} ${padding.top + chartHeight} L ${points[0].x} ${padding.top + chartHeight} Z`;
  const gridLines = [0, 25, 50, 75, 100];

  return (
    <svg viewBox={`0 0 ${width} ${height}`} width="100%" height="300" role="img" aria-label="Score trend chart">
      <defs>
        <linearGradient id="scoreArea" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor="#7C3AED" stopOpacity="0.2" />
          <stop offset="100%" stopColor="#7C3AED" stopOpacity="0.02" />
        </linearGradient>
      </defs>

      {gridLines.map((value) => {
        const y = padding.top + (1 - value / 100) * chartHeight;
        return (
          <g key={value}>
            <line x1={padding.left} x2={width - padding.right} y1={y} y2={y} stroke="#E9EAF3" strokeDasharray="4 6" />
            <text x={padding.left - 14} y={y + 4} textAnchor="end" fill="#94A3B8" fontSize="12">
              {value}
            </text>
          </g>
        );
      })}

      <path d={areaPath} fill="url(#scoreArea)" />
      <path d={path} fill="none" stroke="#7C3AED" strokeLinecap="round" strokeLinejoin="round" strokeWidth="4" />

      {points.map((point, index) => (
        <g key={`${point.name}-${index}`}>
          <circle cx={point.x} cy={point.y} r="5" fill="#7C3AED" stroke="#FFFFFF" strokeWidth="3" />
          <text
            x={point.x}
            y={height - 18}
            textAnchor="middle"
            fill="#70707B"
            fontSize="12"
          >
            {point.name}
          </text>
        </g>
      ))}
    </svg>
  );
}

export function RadarScoreChart({ data }: { data: RadarPoint[] }) {
  const safeData = data.length ? data : [{ label: 'Score', score: 0 }];
  const width = 280;
  const height = 220;
  const centerX = width / 2;
  const centerY = 106;
  const radius = 66;
  const angleStep = (Math.PI * 2) / safeData.length;
  const pointFor = (index: number, scale: number) => {
    const angle = -Math.PI / 2 + index * angleStep;
    return {
      x: centerX + Math.cos(angle) * radius * scale,
      y: centerY + Math.sin(angle) * radius * scale,
    };
  };
  const polygonPoints = safeData
    .map((item, index) => {
      const point = pointFor(index, clampScore(item.score) / 100);
      return `${point.x},${point.y}`;
    })
    .join(' ');

  return (
    <svg viewBox={`0 0 ${width} ${height}`} width="100%" height="220" role="img" aria-label="Skill radar chart">
      {[0.25, 0.5, 0.75, 1].map((scale) => (
        <polygon
          key={scale}
          points={safeData.map((_, index) => {
            const point = pointFor(index, scale);
            return `${point.x},${point.y}`;
          }).join(' ')}
          fill="none"
          stroke="#E9EAF3"
          strokeWidth="1"
        />
      ))}

      {safeData.map((item, index) => {
        const outer = pointFor(index, 1);
        const label = pointFor(index, 1.28);
        return (
          <g key={item.label}>
            <line x1={centerX} x2={outer.x} y1={centerY} y2={outer.y} stroke="#E9EAF3" />
            <text x={label.x} y={label.y} textAnchor="middle" dominantBaseline="middle" fill="#70707B" fontSize="10">
              {item.label}
            </text>
          </g>
        );
      })}

      <polygon points={polygonPoints} fill="#8B5CF6" fillOpacity="0.28" stroke="#7C3AED" strokeWidth="2" />
    </svg>
  );
}
