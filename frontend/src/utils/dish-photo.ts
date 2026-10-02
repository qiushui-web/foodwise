import { publicPath } from "./public-base";

const photos: Record<string, string> = {
  "香菇滑鸡饭": "shiitake-chicken-rice.webp",
  "番茄牛腩饭": "tomato-beef-rice.webp",
  "照烧鸡腿饭": "teriyaki-chicken-rice.webp",
  "鸡胸谷物碗": "chicken-grain-bowl.webp",
  "金枪鱼全麦卷": "tuna-wheat-wrap.webp",
  "红烧牛肉面": "braised-beef-noodles.webp",
  "全麦鸡蛋三明治": "egg-wheat-sandwich.webp",
};

export function dishPhoto(name: string | undefined): string | null {
  const file = name && photos[name];
  return file ? publicPath(`images/dishes/${file}`) : null;
}
