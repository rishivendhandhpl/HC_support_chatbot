// Allow importing CSS as an inlined string (Vite `?inline`).
declare module "*.css?inline" {
  const css: string;
  export default css;
}
