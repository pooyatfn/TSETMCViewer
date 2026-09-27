import { BarChart, HeatmapChart, LineChart, ScatterChart, TreemapChart } from "echarts/charts";
import {
  AxisPointerComponent,
  GridComponent,
  MarkLineComponent,
  TooltipComponent,
} from "echarts/components";
import * as echarts from "echarts/core";
import { SVGRenderer } from "echarts/renderers";
import { useEffect, useRef } from "react";

// Register only what the panel draws: ~1.1 MB → a fraction of that in the bundle.
echarts.use([
  BarChart,
  HeatmapChart,
  LineChart,
  ScatterChart,
  TreemapChart,
  AxisPointerComponent,
  GridComponent,
  MarkLineComponent,
  TooltipComponent,
  SVGRenderer,
]);

export type ChartOption = echarts.EChartsCoreOption;

interface Props {
  option: ChartOption;
  height: number;
  ariaLabel: string;
  onClick?: (params: echarts.ECElementEvent) => void;
}

/**
 * Thin ECharts wrapper: one instance per mount, option replaced on change,
 * resized with its container. SVG renderer keeps text crisp and Vazirmatn-shaped.
 */
export function Chart({ option, height, ariaLabel, onClick }: Props) {
  const el = useRef<HTMLDivElement>(null);
  const inst = useRef<echarts.ECharts | null>(null);
  const clickRef = useRef(onClick);
  clickRef.current = onClick;

  useEffect(() => {
    if (!el.current) return;
    const chart = echarts.init(el.current, undefined, { renderer: "svg" });
    inst.current = chart;
    chart.on("click", (p) => clickRef.current?.(p as echarts.ECElementEvent));
    const ro = new ResizeObserver(() => chart.resize());
    ro.observe(el.current);
    return () => {
      ro.disconnect();
      chart.dispose();
      inst.current = null;
    };
  }, []);

  useEffect(() => {
    inst.current?.setOption(option, { notMerge: true, lazyUpdate: true });
  }, [option]);

  return <div ref={el} className="chart" style={{ height }} role="img" aria-label={ariaLabel} />;
}
