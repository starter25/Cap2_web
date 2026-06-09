declare module "plotly.js-dist-min" {
  // Minimal surface we use. plotly.js-dist-min ships no types, and the full
  // @types/plotly.js pulls heavy transitive deps we don't need here.
  const Plotly: {
    react: (
      root: HTMLElement,
      data: unknown[],
      layout?: Record<string, unknown>,
      config?: Record<string, unknown>,
    ) => Promise<void>;
    purge: (root: HTMLElement) => void;
    Plots: { resize: (root: HTMLElement) => void };
  };
  export default Plotly;
}
