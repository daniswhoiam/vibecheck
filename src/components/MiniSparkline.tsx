import { cn } from "@/lib/utils";
import { useMemo } from "react";

interface MiniSparklineProps {
  data: number[];
  className?: string;
  color?: string;
}

const MiniSparkline = ({ data, className, color = "hsl(var(--primary))" }: MiniSparklineProps) => {
  const { linePath, areaPath, gradientId } = useMemo(() => {
    if (!data || data.length < 2) return { linePath: "", areaPath: "", gradientId: "" };

    const min = Math.min(...data);
    const max = Math.max(...data);
    const range = max - min || 1;
    
    const width = 100;
    const height = 32;
    const paddingY = 4;
    
    // Generate points
    const points = data.map((value, index) => ({
      x: (index / (data.length - 1)) * width,
      y: paddingY + ((max - value) / range) * (height - paddingY * 2),
    }));

    // Create smooth catmull-rom spline
    const catmullRom = (p0: {x: number, y: number}, p1: {x: number, y: number}, p2: {x: number, y: number}, p3: {x: number, y: number}, t: number) => {
      const t2 = t * t;
      const t3 = t2 * t;
      return {
        x: 0.5 * ((2 * p1.x) + (-p0.x + p2.x) * t + (2 * p0.x - 5 * p1.x + 4 * p2.x - p3.x) * t2 + (-p0.x + 3 * p1.x - 3 * p2.x + p3.x) * t3),
        y: 0.5 * ((2 * p1.y) + (-p0.y + p2.y) * t + (2 * p0.y - 5 * p1.y + 4 * p2.y - p3.y) * t2 + (-p0.y + 3 * p1.y - 3 * p2.y + p3.y) * t3),
      };
    };

    let pathPoints: {x: number, y: number}[] = [];
    
    for (let i = 0; i < points.length - 1; i++) {
      const p0 = points[Math.max(0, i - 1)];
      const p1 = points[i];
      const p2 = points[Math.min(points.length - 1, i + 1)];
      const p3 = points[Math.min(points.length - 1, i + 2)];
      
      for (let t = 0; t < 1; t += 0.1) {
        pathPoints.push(catmullRom(p0, p1, p2, p3, t));
      }
    }
    pathPoints.push(points[points.length - 1]);

    const lineD = pathPoints.reduce((acc, point, i) => 
      i === 0 ? `M ${point.x},${point.y}` : `${acc} L ${point.x},${point.y}`, "");
    
    const areaD = `${lineD} L ${width},${height} L 0,${height} Z`;

    return { 
      linePath: lineD, 
      areaPath: areaD, 
      gradientId: `gradient-${Math.random().toString(36).substr(2, 9)}` 
    };
  }, [data]);

  if (!data || data.length < 2) return null;

  return (
    <svg 
      viewBox="0 0 100 32"
      className={cn("w-full h-10", className)}
      preserveAspectRatio="none"
    >
      <defs>
        <linearGradient id={gradientId} x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stopColor={color} stopOpacity="0.3" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path
        d={areaPath}
        fill={`url(#${gradientId})`}
      />
      <path
        d={linePath}
        fill="none"
        stroke={color}
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
};

export default MiniSparkline;
