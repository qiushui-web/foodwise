const metaBase = document.querySelector<HTMLMetaElement>('meta[name="foodwise-base"]')?.content || "/";
export const publicBase = metaBase.endsWith("/") ? metaBase : metaBase + "/";
export const publicPath = (path: string) => publicBase + path.replace(/^\/+/, "");
