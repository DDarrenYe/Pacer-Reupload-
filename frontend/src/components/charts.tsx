import {
  BarElement,
  CategoryScale,
  Chart as ChartJS,
  LinearScale,
  LineElement,
  PointElement,
  Tooltip,
  type ChartOptions,
} from "chart.js";
import { useEffect, useState } from "react";
import { Bar, Line } from "react-chartjs-2";

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, BarElement, Tooltip);

function readColors() {
  const css = getComputedStyle(document.documentElement);
  const v = (name: string) => css.getPropertyValue(name).trim();
  return {
    series: v("--series-1"),
    surface: v("--surface-1"),
    text: v("--text-secondary"),
    muted: v("--text-muted"),
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

interface ChartProps {
  title: string;
  labels: string[];
  values: (number | null)[];
  /** Formats a value for ticks and tooltips. */
  format: (v: number) => string;
}

interface LineProps extends ChartProps {
  /** Pace: lower is better, so flip the axis to put faster at the top. */
  lowerIsBetter?: boolean;
  /** Dashed horizontal guides, e.g. ACWR zone boundaries. Named in the caption. */
  references?: { value: number; label: string }[];
}

function Frame({ title, note, children }: { title: string; note?: string; children: React.ReactNode }) {
  return (
    <figure className="chart">
      <figcaption>
        {title}
        {note && <span className="muted"> ({note})</span>}
      </figcaption>
      <div className="chart-box">{children}</div>
    </figure>
  );
}

/** One series per chart: no legend, the title names it. Never two y-axes. */
export function LineChart({ title, labels, values, format, lowerIsBetter, references = [] }: LineProps) {
  const c = useChartColors();
  const options: ChartOptions<"line"> = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: "index", intersect: false },
    plugins: {
      legend: { display: false },
      tooltip: {
        // Only the data series gets a tooltip row; reference lines are explained in the caption.
        filter: (item) => item.datasetIndex === 0,
        callbacks: { label: (ctx) => `${title}: ${format(ctx.parsed.y ?? 0)}` },
      },
    },
    scales: {
      x: { grid: { display: false }, ticks: { color: c.text, maxTicksLimit: 8 }, border: { color: c.grid } },
      y: {
        reverse: lowerIsBetter,
        grid: { color: c.grid },
        border: { display: false },
        ticks: { color: c.text, callback: (v) => format(Number(v)), maxTicksLimit: 5 },
        grace: "10%",
      },
    },
  };
  const notes = [];
  if (lowerIsBetter) notes.push("faster is higher");
  if (references.length) notes.push(`dashed lines: ${references.map((r) => r.label).join(", ")}`);
  const note = notes.join("; ");
  // Dense daily series: markers only on hover, or the dots swamp the line.
  const dense = values.length > 30;
  return (
    <Frame title={title} note={note || undefined}>
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
              pointRadius: dense ? 0 : 4,
              pointHoverRadius: 6,
              pointBorderColor: c.surface,
              pointBorderWidth: 2,
              spanGaps: true,
            },
            ...references.map((r) => ({
              data: labels.map(() => r.value),
              borderColor: c.muted,
              borderWidth: 1,
              borderDash: [4, 4],
              pointRadius: 0,
              pointHoverRadius: 0,
            })),
          ],
        }}
      />
    </Frame>
  );
}

export function BarChart({ title, labels, values, format }: ChartProps) {
  const c = useChartColors();
  const options: ChartOptions<"bar"> = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      tooltip: { callbacks: { label: (ctx) => `${title}: ${format(ctx.parsed.y ?? 0)}` } },
    },
    scales: {
      x: { grid: { display: false }, ticks: { color: c.text, maxTicksLimit: 8 }, border: { color: c.grid } },
      y: {
        beginAtZero: true,
        grid: { color: c.grid },
        border: { display: false },
        ticks: { color: c.text, callback: (v) => format(Number(v)), maxTicksLimit: 5 },
      },
    },
  };
  return (
    <Frame title={title}>
      <Bar
        options={options}
        data={{
          labels,
          datasets: [
            {
              data: values,
              backgroundColor: c.series,
              borderRadius: { topLeft: 4, topRight: 4 },
              borderSkipped: "bottom",
              maxBarThickness: 28,
            },
          ],
        }}
      />
    </Frame>
  );
}
