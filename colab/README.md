# 👗 StyleVision — Google Colab CatVTON GPU Server Setup

This guide walks you through running the real **CatVTON Neural Diffusion Pipeline** on a free **NVIDIA T4 GPU** in Google Colab.

---

## 🌟 Why Colab GPU?
- **Keeps 100% of User's Body & Pose**: Face, hair, skin tone, hands, body posture, and background remain completely unchanged.
- **True Clothing Replacement**: Replaces existing clothing (e.g. kurti, t-shirt) with any target saree, gown, dress, or top seamlessly using AI diffusion.
- **Zero Cost**: Runs entirely on Google Colab's free NVIDIA T4 GPU (15 GB VRAM).

---

## 🚀 3 Simple Steps to Start the AI Server

### Step 1: Open the Notebook in Google Colab
1. Go to [Google Colab](https://colab.research.google.com/).
2. Click **Upload** tab.
3. Select `backend/colab/catvton_gpu_server.ipynb` from your computer.

### Step 2: Enable Free GPU & Run All
1. In Colab, click **Runtime** in the top menu -> **Change runtime type**.
2. Select **T4 GPU** under Hardware Accelerator, then click **Save**.
3. Click **Runtime** -> **Run all** (or press `Ctrl + F9`).
4. Wait ~3–4 minutes for the models to load.

### Step 3: Copy the Public URL into Your Backend
At the bottom of Cell 4, you will see a banner like this:

```
===========================================================================
🎉 STYLEVISION CatVTON GPU SERVER IS RUNNING!
👉 PUBLIC URL: https://stylish-paris-abc.trycloudflare.com
===========================================================================
```

1. Copy that `https://....trycloudflare.com` URL.
2. In your laptop, open `backend/.env` and update:
   ```env
   TRYON_MODE=catvton
   CATVTON_ENDPOINT=https://stylish-paris-abc.trycloudflare.com
   ```
3. Save the `.env` file. The backend automatically detects the endpoint!
4. On your mobile phone, open the StyleVision app, select your photo and a dress/saree, and tap **Try On**!

---

## 🛠️ API Reference
- **Health Check**: `GET /health` -> `{"status": "online", "device": "Tesla T4", "vram_allocated_gb": 7.4}`
- **Virtual Try-On**: `POST /tryon`
  - `person_image`: Image file (PNG/JPG)
  - `cloth_image`: Image file (PNG/JPG)
  - `cloth_type`: `"overall"` (dresses, sarees, gowns) | `"upper"` (tops, kurtis) | `"lower"` (skirts, pants)
  - Returns: `image/png` (synthesized try-on image preserving posture)
