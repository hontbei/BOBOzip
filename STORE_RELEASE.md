# 微软商店正式发布指南

本指南覆盖把 BOBOzip 上架到微软商店（付费 ¥1）的完整流程。
带 ⚙️ 的步骤是我（自动化/脚本）已经准备好的；带 👤 的步骤必须你本人在
Partner Center 操作，因为涉及账号、身份与付款信息。

---

## 第 1 步 👤 注册开发者账号

1. 打开 https://partner.microsoft.com/dashboard 用你的微软账号登录
2. 注册个人开发者账号，一次性费用约 $19（人民币结算约 ¥130）
3. 完成身份验证（个人账号需要真实姓名/地址；可能需要 1-2 天审核）

## 第 2 步 👤 创建应用并保留名称

1. Dashboard → Apps and games → New product → MSIX or PWA app
2. 输入应用名 `BOBOzip`（若被占用，换一个，例如 `BOBOzip Unzip`）
3. 保留成功后，应用就创建好了

## 第 3 步 👤 获取你的 Identity 值（关键）

进入该应用 → Product management → Product identity，记下三项：

- **Package/Identity/Name**：形如 `12345PublisherName.BOBOzip`
- **Package/Identity/Publisher**：形如 `CN=ABCDEF12-3456-7890-ABCD-1234567890AB`
- **Publisher display name**：你的发布者显示名

> 这三项必须和提交包里的清单**完全一致**，否则商店拒收。

## 第 4 步 👤 把 Identity 值填进自动构建

编辑 `.github/workflows/build.yml`，把 store 包构建那行改成你的真实值
（把下面三个值替换成上一步记下的内容）：

```yaml
      - name: Build MSIX package (store, unsigned)
        shell: pwsh
        run: >
          ./packaging/build_msix.ps1
          -ExePath dist/BOBOzip.exe -OutputDir dist -Store
          -IdentityName "12345PublisherName.BOBOzip"
          -Publisher "CN=ABCDEF12-3456-7890-ABCD-1234567890AB"
          -PublisherDisplayName "你的发布者显示名"
```

提交后打一个新 tag（见第 5 步）即可生成商店专用包。

> 如果你不想把 Identity 写进公开/私有仓库，也可以在本地用同样参数手动跑
> `packaging/build_msix.ps1 -Store ...` 生成包再上传。

## 第 5 步 ⚙️ 触发构建拿到商店包

```bash
git tag v1.0.0
git push origin v1.0.0
```

GitHub Actions 跑完后，在 Release 附件里下载 **`BOBOzip-store.msix`**
（注意：不是 `BOBOzip.msix`，那个是本地测试用的自签名版）。

## 第 6 步 👤 在 Partner Center 提交

为该应用新建一个 Submission，依次填写：

1. **Pricing and availability**
   - 价格选 ¥1（最低档，商店有固定价格梯度，¥1 通常可选）
   - 选择上架的国家/地区
2. **Properties**
   - 分类：Utilities & tools
   - 隐私政策 URL：如果应用不联网收集数据，仍建议提供一个简单声明页
3. **Age ratings**：如实填写（本应用无成人内容，注意默认密码已清空）
4. **Packages**：上传 `BOBOzip-store.msix`
5. **Store listing**
   - 描述：强调"管理你自己的加密压缩包"，避免"破解/爆破密码"等措辞
   - 至少 1 张截图（主界面）
6. 提交审核（通常 1-3 个工作日）

## 第 7 步 👤 审核要点（避免被拒）

- ✅ 默认不含任何密码（已处理，全新安装为空密码库）
- ✅ 删除压缩包默认关闭（已处理）
- ✅ 描述使用合规措辞
- ⚠️ 截图不要出现任何成人网站/不当内容
- ⚠️ 如被质疑"密码破解工具"，在审核备注里说明用途是解压用户自己拥有的加密文件

---

## 常见疑问

**为什么商店包不签名？**
你上传的是未签名包，微软商店会用自己的证书重新签名。用户从商店安装时零障碍，
不会出现 `0x800B010A` 那种证书信任错误。本地测试才需要自签名版。

**¥1 我能拿到多少？**
微软对应用销售抽成（通常开发者拿约 85%）。¥1 基本是象征性定价，实际到手很少，
适合"打个标记/做作品集"，不适合靠它赚钱。

**Identity 值会泄露吗？**
Publisher（CN=...）和 Name 不是机密，它们会公开存在于已发布的包里，写进仓库没有
安全风险。真正的机密是账号密码和签名私钥，这些都不在仓库里。
