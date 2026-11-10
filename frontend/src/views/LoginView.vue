<script setup lang="ts">
import { publicPath } from "../utils/public-base";
</script>

<template>
  <main class="login-shell">
    <section class="login-brand" :style="{ '--login-cover': `url('${publicPath('images/canteen-wide.jpg')}')` }">
      <img :src="publicPath('images/brand-logo-blue-transparent.png')" alt="食刻有数品牌标识" />
      <span>高校餐饮精细化经营与食品减损服务</span>
      <h1>让每一份备餐<br /><em>更有依据</em></h1>
      <p>统一管理经营台账、备餐建议、限时优惠、订单核销和经营复盘。</p>
    </section>
    <section class="login-card">
      <div>
        <span class="kicker">OPERATION PORTAL</span>
        <h2>进入经营工作台</h2>
        <p>请使用运营账号登录</p>
      </div>
      <form method="post" :action="publicPath('login')">
        <label>账号<input name="username" autocomplete="username" required /></label>
        <label>密码<input name="password" type="password" autocomplete="current-password" required /></label>
        <p v-if="$route.query.error" class="login-error">账号或密码不正确</p>
        <button class="btn primary wide" type="submit">登录经营工作台</button>
      </form>
      <small><i></i>账号由食堂运营方统一配置</small>
    </section>
  </main>
</template>

<style scoped>
.login-shell{min-height:540px;width:min(1040px,92vw);display:grid;grid-template-columns:1.12fr .88fr;border-radius:8px;overflow:hidden;background:#fff;border:1px solid #dce7eb;box-shadow:0 24px 64px rgba(39,66,82,.12);position:relative;z-index:1}.login-brand{padding:62px;background-image:linear-gradient(110deg,rgba(239,247,249,.96),rgba(237,246,249,.84)),var(--login-cover);background-position:center;background-size:cover;color:#263f4e}.login-brand img{width:72px;height:72px;object-fit:contain;margin-bottom:28px}.login-brand span{display:block;font-size:13px;color:#526e7c}.login-brand h1{font-size:40px;line-height:1.25;margin:18px 0;color:#263f4e}.login-brand h1 em{font-style:normal;color:#557f96}.login-brand p{max-width:440px;font-size:14px;line-height:1.8;color:#526b78}.login-card{padding:62px 52px;display:flex;flex-direction:column;justify-content:center}.login-card h2{font-size:25px;margin:6px 0;color:#263c49}.login-card>div>p{font-size:14px;color:#687b85}.login-card form{display:grid;gap:18px;margin:27px 0}.login-card label{display:grid;gap:9px;font-size:13px;color:#61737c}.login-card input{height:48px;border:1px solid #d6e2e6;border-radius:6px;padding:0 13px;outline:none;background:#f6f9fa;font-size:15px}.login-card input:focus{border-color:#6e93a5;box-shadow:0 0 0 3px rgba(79,128,150,.12)}.login-card>small{font-size:12px;color:#788991;display:flex;align-items:center;gap:7px}.login-card>small i{width:7px;height:7px;border-radius:50%;background:#4b8c92}.login-error{color:#b64e52;font-size:13px}.btn{min-height:46px;border:0;border-radius:6px;padding:12px 16px;font-size:14px;cursor:pointer}.btn.primary{background:#426d83;color:#fff;font-weight:700}.btn.primary:hover{background:#315a70}.btn:disabled{opacity:.65;cursor:wait}
@media(max-width:760px){.login-shell{width:min(480px,92vw);grid-template-columns:1fr;min-height:0;border-radius:20px}.login-brand{display:grid;grid-template-columns:52px minmax(0,1fr);grid-template-rows:auto auto;align-items:center;column-gap:12px;padding:20px 24px 16px}.login-brand img{grid-row:1/3;width:52px;height:52px;margin:0}.login-brand span{font-size:12px}.login-brand h1{font-size:23px;line-height:1.2;margin:4px 0 0}.login-brand p{display:none}.login-card{padding:30px 26px 34px}}
</style>
