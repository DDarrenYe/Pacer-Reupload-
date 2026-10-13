import CompareCard from "../components/CompareCard";
import { useTitle } from "../useTitle";

/** Your rank and how your times compare with runners of your age and sex. */
export default function Rank() {
  useTitle("Rank");
  return (
    <main>
      <h1>Rank</h1>
      <CompareCard />
    </main>
  );
}
