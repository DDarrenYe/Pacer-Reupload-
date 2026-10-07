import {
  CategoryScale,
  Chart as ChartJS,
  LinearScale,
  LineElement,
  PointElement,
  Tooltip,
  type ChartOptions,
} from "chart.js";
import { useEffect, useState } from "react";
import { Line } from "react-chartjs-2";

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Tooltip);

interface Props {
  title: string;
  labels: string[];
  values: (number | null)[];
  /** Formats a value for ticks and tooltips. */
  format: (v: number) => string;
  /** Pace: lower is better, so flip the axis to put faster at the top. */
  lowerIsBetter?: boolean;
}

function readColors() {
  const css = getComputedStyle(document.documentElement);
  const v = (name: string) => css.getPropertyValue(name).trim();
  return {
    series: v("--series-1"),
    surface: v("--surface-1"),
    text: v("--text-secondary"),
    grid: v("--grid"),
  };
}

/** Re-read the CSS colour tokens when the OS switches light/dark. */
function useChartColors() {
  const [colors, setColors] = useState(readColors);
  useEffect(() => {
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const update = () => setColors(readColors());
    mq.addEventListener("change", update);
    return () => mq.removeEventListener("change", update);
  }, []);
  return colors;
}

/** One series per chart: no legend, the title names it. Never two y-axes. */
export default function SplitChart({ title, labels, values, format, lowerIsBetter }: Props) {
  const c = useChartColors();
  const options: ChartOptions<"line"> = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: "index", intersect: false },
    plugins: {
      legend: { display: false },
      tooltip: {
        callbacks: { label: (ctx) => `${title}: ${format(ctx.parsed.y ?? 0)}` },
      },
    },
    scales: {
      x: { grid: { display: false }, ticks: { color: c.text }, border: { color: c.grid } },
      y: {
        reverse: lowerIsBetter,
        grid: { color: c.grid },
        border: { display: false },
        ticks: { color: c.text, callback: (v) => format(Number(v)), maxTicksLimit: 5 },
        grace: "10%",
      },
    },
  };
  return (
    <figure className="chart">
      <figcaption>
        {title}
        {lowerIsBetter && <span className="muted"> (faster is higher)</span>}
      </figcaption>
      <div className="chart-box">
        <Line
          options={options}
          data={{
            labels,
            datasets: [
              {
                data: values,
                borderColor: c.series,
                backgroundColor: c.series,
                borderWidth: 2,
                pointRadius: 4,
                pointHoverRadius: 6,
                pointBorderColor: c.surface,
                pointBorderWidth: 2,
                spanGaps: true,
              },
            ],
          }}
        />
      </div>
    </figure>
  );
}
