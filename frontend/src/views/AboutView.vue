<script setup lang="ts">
import { RouterLink } from "vue-router";
</script>

<template>
  <div class="about-view">
    <span class="kicker">使用说明</span>
    <h2>第一次使用食刻有数</h2>
    <p class="lead">这是给食堂经营人员使用的辅助工具：把真实经营台账变成备餐建议，再把执行结果记回台账。下面按实际操作顺序说明。</p>

    <section class="guide-block"><h3>使用前准备</h3><ul><li>向管理员获取账号；正式服务器需要先登录。</li><li>核对档口、菜品和菜品编号。预测所选菜品必须已有历史销量。</li><li>准备经营记录：日期、菜品、计划与实际备餐、售出、优惠售出、剩余、收入和天气。</li><li>每天确认考试周、校园活动、现场库存及食品安全状况。</li></ul><RouterLink to="/app/stalls">先核对档口与菜品 →</RouterLink></section>

    <section class="guide-block"><h3>按餐次操作</h3><div class="steps"><article><b>01</b><strong>先录入历史数据</strong><p>在“录入或导入台账”中单条填写，或先预览 CSV 再批量导入。没有真实记录时，只把预置数据用于演示。</p><RouterLink to="/app/operations/feedback">去录入数据 →</RouterLink></article><article><b>02</b><strong>营业前生成预测</strong><p>选择菜品、预计天气、考试周和校园活动。先看首批备餐量，再根据现场销售决定是否补餐。</p><RouterLink to="/app/prediction">去生成建议 →</RouterLink></article><article><b>03</b><strong>营业中处理剩余</strong><p>在安全售卖时段内核对优惠建议；顾客实际取餐后，再在订单页核销已有订单。</p><RouterLink to="/app/offers">去看优惠 →</RouterLink></article><article><b>04</b><strong>闭餐后回传与复盘</strong><p>填写真实备餐、售出、剩余和收入。定期查看预警、经营报告及减损分析。</p><RouterLink to="/app/reports">去看复盘 →</RouterLink></article></div></section>

    <section class="guide-block"><h3>关键数据怎么填</h3><div class="definitions"><div><strong>实际备餐</strong><span>这餐最终制作的数量。</span></div><div><strong>实际售出</strong><span>原价和优惠销售的总数量。</span></div><div><strong>优惠售出</strong><span>实际售出中的一部分，不再重复相加。</span></div><div><strong>闭餐剩余</strong><span>这餐结束时没有售出的数量。</span></div></div><p class="formula">校验关系：实际备餐 = 实际售出 + 闭餐剩余。</p></section>

    <section class="guide-block limits"><h3>使用边界</h3><p>预测数量和停做时间是辅助建议，不能替代现场判断与食品安全确认。当前不会自动从 POS、刷卡机或学生端读取销售数据；经营人员仍需主动录入或导入台账。订单页只核销系统中已有的订单。</p></section>
    <section id="photo-credits" class="guide-block limits"><h3>菜品图片来源</h3><p>菜品图片为 Wikimedia Commons 上的同类食物实拍，经过缩放与 WebP 格式转换。它们不是本系统档口的实际出品，也不用于判断库存或食品安全。</p>
      <ul class="photo-credits">
        <li>香菇滑鸡饭示意：<a href="https://commons.wikimedia.org/wiki/File:HK_Kwun_Tong_Lunch_Box_dim_sum_mushroom_chicken_rice_Nov_2018_01.jpg" target="_blank" rel="noopener noreferrer">Manfilliomia</a>，CC BY-SA 4.0</li>
        <li>番茄牛腩饭示意：<a href="https://commons.wikimedia.org/wiki/File:Baked_rice_with_Beef_tongue_and_tomato_sauce_from_Cafe_De_Coral.jpg" target="_blank" rel="noopener noreferrer">Peachyeung316</a>，CC BY-SA 4.0</li>
        <li>照烧鸡腿饭示意：<a href="https://commons.wikimedia.org/wiki/File:Donburi_Rice_bowl_of_Chicken_Teriyaki_with_Tomato.jpg" target="_blank" rel="noopener noreferrer">TechnoKittyCat</a>，CC0</li>
        <li>鸡胸谷物碗示意：<a href="https://commons.wikimedia.org/wiki/File:Liat_Portal_for_Foodie_Disorder_-_Roasted_chicken_with_cauliflower_broccoli_potatoes_rice_and_salad.jpg" target="_blank" rel="noopener noreferrer">HaJunkiyada</a>，CC BY-SA 4.0</li>
        <li>金枪鱼全麦卷示意：<a href="https://commons.wikimedia.org/wiki/File:Tuna_wrap,_Delft_(2018).jpg" target="_blank" rel="noopener noreferrer">Donald Trung Quoc Don</a>，CC BY-SA 4.0</li>
        <li>红烧牛肉面示意：<a href="https://commons.wikimedia.org/wiki/File:Beef_Noodle_Soup_(braised_beef_shank,_mustard_greens,_baby_bok_choy)_July_2023.JPG" target="_blank" rel="noopener noreferrer">Benoît Prieur</a>，CC0</li>
        <li>全麦鸡蛋三明治示意：<a href="https://commons.wikimedia.org/wiki/File:Egg_Sandwich_001.jpg" target="_blank" rel="noopener noreferrer">Ocdp</a>，CC0</li>
      </ul>
      <p>CC BY-SA 4.0 的许可文本见 <a href="https://creativecommons.org/licenses/by-sa/4.0/" target="_blank" rel="noopener noreferrer">Creative Commons</a>。</p>
    </section>
  </div>
</template>

<style scoped>
.about-view{padding:32px;background:#fff;border:1px solid #dce8f2;border-radius:12px}.kicker{font-size:11px;color:#3478c9;font-weight:700}.about-view h2{font-size:29px;margin:9px 0}.lead{max-width:780px;font-size:14px;line-height:1.8;color:#536f87}.guide-block{border-top:1px solid #e0ebf3;padding-top:22px;margin-top:24px}.guide-block h3{font-size:18px;margin:0 0 14px;color:#254d72}.guide-block ul{padding-left:20px;margin:0 0 14px;color:#526f86;font-size:13px;line-height:1.9}.guide-block a{font-size:13px;font-weight:700;color:#286daf}.steps{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.steps article{padding:18px;border:1px solid #d9e8f3;background:#f7fbff;border-radius:10px}.steps b,.steps strong{display:block}.steps b{font-size:12px;color:#3478c9}.steps strong{font-size:15px;margin-top:8px}.steps p,.limits p{color:#58748b;font-size:13px;line-height:1.8}.definitions{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.definitions div{padding:12px 15px;background:#f4f8fc;border-radius:8px}.definitions strong,.definitions span{display:block;font-size:13px}.definitions span{margin-top:5px;color:#5c7890}.formula{font-size:13px;font-weight:700;color:#286daf}@media(max-width:700px){.about-view{padding:22px 18px}.steps,.definitions{grid-template-columns:1fr}}
</style>
<style scoped>
.photo-credits{columns:2;column-gap:30px}.photo-credits li{break-inside:avoid}@media(max-width:700px){.photo-credits{columns:1}}
</style>
