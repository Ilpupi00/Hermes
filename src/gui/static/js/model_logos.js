/* =============================================================
   HERMES — model_logos.js
   Logo SVG inline per i principali provider AI.
   Riconoscimento automatico del provider dal nome modello.
   Precaricamento immagini al boot.
   ============================================================= */

/**
 * Mappa provider → { svg, color, label }
 * SVG sono ottimizzati e inline per zero-latency rendering.
 */
const AI_PROVIDERS = {

  openai: {
    label: 'OpenAI',
    color: '#10a37f',
    bg: 'rgba(16,163,127,0.12)',
    svg: `<svg viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
      <path d="M22.282 9.821a5.985 5.985 0 0 0-.516-4.91 6.046 6.046 0 0 0-6.51-2.9A6.065 6.065 0 0 0 4.981 4.18a5.985 5.985 0 0 0-3.998 2.9 6.046 6.046 0 0 0 .743 7.097 5.98 5.98 0 0 0 .51 4.911 6.051 6.051 0 0 0 6.515 2.9A5.985 5.985 0 0 0 13.26 24a6.056 6.056 0 0 0 5.772-4.206 5.99 5.99 0 0 0 3.997-2.9 6.056 6.056 0 0 0-.747-7.073zM13.26 22.43a4.476 4.476 0 0 1-2.876-1.04l.141-.081 4.779-2.758a.795.795 0 0 0 .392-.681v-6.737l2.02 1.168a.071.071 0 0 1 .038.052v5.583a4.504 4.504 0 0 1-4.494 4.494zM3.6 18.304a4.47 4.47 0 0 1-.535-3.014l.142.085 4.783 2.759a.771.771 0 0 0 .78 0l5.843-3.369v2.332a.08.08 0 0 1-.033.062L9.74 19.95a4.5 4.5 0 0 1-6.14-1.646zM2.34 7.896a4.485 4.485 0 0 1 2.366-1.973V11.6a.766.766 0 0 0 .388.677l5.815 3.355-2.02 1.168a.076.076 0 0 1-.071 0l-4.83-2.786A4.504 4.504 0 0 1 2.34 7.872zm16.597 3.855l-5.843-3.371 2.019-1.168a.076.076 0 0 1 .072 0l4.83 2.791a4.494 4.494 0 0 1-.676 8.105v-5.678a.79.79 0 0 0-.402-.679zm2.008-3.023l-.141-.085-4.774-2.782a.776.776 0 0 0-.785 0L9.409 9.23V6.897a.066.066 0 0 1 .028-.061l4.83-2.787a4.5 4.5 0 0 1 6.68 4.66zm-12.64 4.135l-2.02-1.164a.08.08 0 0 1-.038-.057V6.075a4.5 4.5 0 0 1 7.375-3.453l-.142.08L8.704 5.46a.795.795 0 0 0-.393.681zm1.097-2.365l2.602-1.5 2.607 1.5v2.999l-2.597 1.5-2.607-1.5z"/>
    </svg>`
  },

  anthropic: {
    label: 'Anthropic',
    color: '#d4a27f',
    bg: 'rgba(212,162,127,0.12)',
    svg: `<svg viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
      <path d="M13.827 3.52h3.603L24 20h-3.603l-6.57-16.48zm-7.258 0h3.767L16.906 20h-3.674l-1.343-3.461H5.017L3.674 20H0L6.569 3.52zm4.132 9.959L8.453 7.687 6.205 13.48h4.496z"/>
    </svg>`
  },

  meta: {
    label: 'Meta / Llama',
    color: '#0082fb',
    bg: 'rgba(0,130,251,0.12)',
    svg: `<svg viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
      <path d="M6.915 4.03c-1.968 0-3.683 1.28-4.871 3.113C.704 9.208 0 11.883 0 14.449c0 .706.07 1.369.21 1.973a6.624 6.624 0 0 0 .265.86 5.297 5.297 0 0 0 .371.761c.696 1.159 1.818 1.927 3.593 1.927 1.497 0 2.633-.671 3.965-2.444.76-1.012 1.144-1.626 2.663-4.32l.756-1.339.186-.325c.186.325.376.648.57.968l.403.704c1.555 2.728 2.556 4.113 3.769 5.09 1.271.993 2.701 1.126 3.903 1.126 2.72 0 4.783-2.162 4.783-5.334 0-2.548-.61-5.079-1.909-7.056-1.283-1.952-3.042-3.078-5.041-3.078-2.053 0-3.927 1.284-5.562 3.8-1.285-2.511-3.135-3.8-5.134-3.8zm.036 3.285c.573 0 1.218.572 1.878 1.715l.293.522.456.82c-.83 1.481-1.26 2.24-1.501 2.657l-.291.522-.33.586c-.773 1.356-1.166 1.836-1.596 1.836-.36 0-.612-.244-.78-.584a5.57 5.57 0 0 1-.47-2.498c0-1.929.47-3.891 1.266-5.115.307-.472.684-.461.684-.461zm10.696.457c1.057 0 2.042.812 2.88 2.233.856 1.449 1.348 3.454 1.348 5.303 0 1.801-.627 2.603-1.594 2.603-.609 0-1.208-.28-1.84-.83-.956-.825-1.808-2.043-3.119-4.297l-.39-.682-.507-.888c1.354-2.617 2.38-3.442 3.222-3.442z"/>
    </svg>`
  },

  mistral: {
    label: 'Mistral AI',
    color: '#ff7000',
    bg: 'rgba(255,112,0,0.12)',
    svg: `<svg viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
      <path d="M0 0h4v4H0zm6.667 0h4v4h-4zM0 6.667h4v4H0zm6.667 0h4v4h-4zM13.333 0h4v4h-4zM20 0h4v4h-4zm-6.667 6.667h4v4h-4zM20 6.667h4v4h-4zM0 13.333h4v4H0zm6.667 0h4v4h-4zm6.666 0h4v4h-4zm6.667 0h4v4h-4zM0 20h4v4H0zm13.333 0h4v4h-4zM20 20h4v4h-4z"/>
    </svg>`
  },

  google: {
    label: 'Google / Gemini',
    color: '#4285f4',
    bg: 'rgba(66,133,244,0.12)',
    svg: `<svg viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
      <path d="M12 11.1459L12 9H22.0003C22.1565 9.65668 22.2396 10.3393 22.2396 11.0454C22.2396 14.0681 21.1702 16.6327 19.2979 18.3956L19.2983 18.396L16.3179 15.9301C17.3718 15.2076 18.1622 14.1131 18.5103 12.8284L12 12.8284L12 11.1459Z" fill="#4285F4"/>
      <path d="M5.25601 13.6659C5.08705 13.1448 4.9939 12.5855 4.9939 12.0001C4.9939 11.4146 5.08705 10.8553 5.25601 10.3342L2.33001 7.92725C1.79142 9.10455 1.5 10.5169 1.5 12.0001C1.5 13.483 1.79134 14.8951 2.32981 16.0723L5.25601 13.6659Z" fill="#FBBC05"/>
      <path d="M12.0001 4.76114C13.5437 4.76114 14.9316 5.30826 16.0228 6.19838L18.6773 3.54393C17.0138 2.02264 14.7974 1.08594 12.0001 1.08594C8.14404 1.08594 4.82208 3.29019 3.15576 6.50993L6.08183 8.91687C6.88688 6.55038 9.24988 4.76114 12.0001 4.76114Z" fill="#EA4335"/>
      <path d="M12.0001 19.2388C9.24988 19.2388 6.88688 17.4495 6.08183 15.083L3.15576 17.49C4.82208 20.7097 8.14404 22.914 12.0001 22.914C14.6928 22.914 16.8577 22.0679 18.4975 20.6116L15.7083 18.2228C14.8307 18.8817 13.5321 19.2388 12.0001 19.2388Z" fill="#34A853"/>
    </svg>`
  },

  huggingface: {
    label: 'HuggingFace',
    color: '#ff9d00',
    bg: 'rgba(255,157,0,0.12)',
    svg: `<svg viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
      <path d="M12 0C5.373 0 0 5.373 0 12s5.373 12 12 12 12-5.373 12-12S18.627 0 12 0zm0 2.4a9.6 9.6 0 1 1 0 19.2A9.6 9.6 0 0 1 12 2.4zm-3.6 8.4a1.2 1.2 0 1 0 0 2.4 1.2 1.2 0 0 0 0-2.4zm7.2 0a1.2 1.2 0 1 0 0 2.4 1.2 1.2 0 0 0 0-2.4zm-3.6 4.8c-1.98 0-3.6 1.08-3.6 2.4h7.2c0-1.32-1.62-2.4-3.6-2.4zM8.4 6a1.8 1.8 0 0 0-1.8 1.8A1.8 1.8 0 0 0 8.4 9.6a1.8 1.8 0 0 0 1.8-1.8A1.8 1.8 0 0 0 8.4 6zm7.2 0a1.8 1.8 0 0 0-1.8 1.8 1.8 1.8 0 0 0 1.8 1.8 1.8 1.8 0 0 0 1.8-1.8A1.8 1.8 0 0 0 15.6 6z"/>
    </svg>`
  },

  ollama: {
    label: 'Ollama',
    color: '#ffffff',
    bg: 'rgba(255,255,255,0.08)',
    svg: `<svg viewBox="0 0 50 50" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
      <circle cx="25" cy="25" r="20" fill="none" stroke="currentColor" stroke-width="3"/>
      <circle cx="18" cy="22" r="3"/>
      <circle cx="32" cy="22" r="3"/>
      <path d="M17 32 Q25 38 33 32" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"/>
    </svg>`
  },

  cohere: {
    label: 'Cohere',
    color: '#39594d',
    bg: 'rgba(57,89,77,0.25)',
    svg: `<svg viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
      <path d="M22.045 8.462A10.696 10.696 0 0 0 12 1.5C6.201 1.5 1.5 6.201 1.5 12c0 4.163 2.387 7.777 5.882 9.607 2.178 1.133 3.629.157 3.629-1.764V14.16c0-1.92-1.53-3.697-3.45-3.697a3.67 3.67 0 0 0-1.255.223 8.27 8.27 0 0 1-.194-1.75 8.118 8.118 0 0 1 8.118-8.119c1.998 0 3.831.722 5.252 1.916-.42.514-.672 1.174-.672 1.895 0 1.657 1.343 3 3 3s3-1.343 3-3a3.003 3.003 0 0 0-2.765-2.166z"/>
    </svg>`
  },

  deepseek: {
    label: 'DeepSeek',
    color: '#4d6bfe',
    bg: 'rgba(77,107,254,0.12)',
    svg: `<svg viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
      <path d="M23.748 9.817c-.13-.193-.544-.762-1.234-.762-.423 0-.796.212-1.105.495a10.26 10.26 0 0 0-2.202-3.218c-.43-.412-.876-.766-1.31-1.08a10.18 10.18 0 0 0-1.458-.868c-3.407-1.68-7.52-1.197-10.472 1.285C4.02 7.29 2.602 9.825 2.602 12.573c0 3.41 1.756 6.604 4.648 8.52 2.88 1.904 6.56 2.269 9.744.95a10.27 10.27 0 0 0 3.76-2.748c.97-1.148 1.65-2.486 2.004-3.91.143-.572.235-1.16.27-1.748a.755.755 0 0 0 .008-.107c.03-.748-.082-1.51-.288-2.713zm-9.3 7.8c-2.876 0-5.212-2.335-5.212-5.213 0-2.876 2.336-5.212 5.213-5.212 2.877 0 5.212 2.336 5.212 5.212 0 2.878-2.335 5.213-5.212 5.213z"/>
    </svg>`
  },

  microsoft: {
    label: 'Microsoft / Phi',
    color: '#00a4ef',
    bg: 'rgba(0,164,239,0.12)',
    svg: `<svg viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
      <path d="M11.4 24H0V12.6h11.4V24zM24 24H12.6V12.6H24V24zM11.4 11.4H0V0h11.4v11.4zM24 11.4H12.6V0H24v11.4z"/>
    </svg>`
  },

  qwen: {
    label: 'Alibaba / Qwen',
    color: '#ff6a00',
    bg: 'rgba(255,106,0,0.12)',
    svg: `<svg viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
      <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 15v-4H7l5-8v4h4l-5 8z"/>
    </svg>`
  },

  gemma: {
    label: 'Google / Gemma',
    color: '#4285f4',
    bg: 'rgba(66,133,244,0.12)',
    svg: `<svg viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
      <path d="M12 11.1459L12 9H22.0003C22.1565 9.65668 22.2396 10.3393 22.2396 11.0454C22.2396 14.0681 21.1702 16.6327 19.2979 18.3956L19.2983 18.396L16.3179 15.9301C17.3718 15.2076 18.1622 14.1131 18.5103 12.8284L12 12.8284L12 11.1459Z" fill="#4285F4"/>
      <path d="M5.25601 13.6659C5.08705 13.1448 4.9939 12.5855 4.9939 12.0001C4.9939 11.4146 5.08705 10.8553 5.25601 10.3342L2.33001 7.92725C1.79142 9.10455 1.5 10.5169 1.5 12.0001C1.5 13.483 1.79134 14.8951 2.32981 16.0723L5.25601 13.6659Z" fill="#FBBC05"/>
      <path d="M12.0001 4.76114C13.5437 4.76114 14.9316 5.30826 16.0228 6.19838L18.6773 3.54393C17.0138 2.02264 14.7974 1.08594 12.0001 1.08594C8.14404 1.08594 4.82208 3.29019 3.15576 6.50993L6.08183 8.91687C6.88688 6.55038 9.24988 4.76114 12.0001 4.76114Z" fill="#EA4335"/>
      <path d="M12.0001 19.2388C9.24988 19.2388 6.88688 17.4495 6.08183 15.083L3.15576 17.49C4.82208 20.7097 8.14404 22.914 12.0001 22.914C14.6928 22.914 16.8577 22.0679 18.4975 20.6116L15.7083 18.2228C14.8307 18.8817 13.5321 19.2388 12.0001 19.2388Z" fill="#34A853"/>
    </svg>`
  },

  // Provider generico / fallback
  local: {
    label: 'Local Server',
    color: '#6366f1',
    bg: 'rgba(99,102,241,0.12)',
    svg: `<svg viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
      <path d="M22 9V7h-2V5c0-1.1-.9-2-2-2H4c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2v-2h2v-2h-2v-2h2v-2h-2V9h2zm-4 10H4V5h14v14z"/>
      <circle cx="9" cy="12" r="2"/>
      <path d="M13 12h4"/>
    </svg>`
  },

  // ── Hermes (pipeline locale, branding proprio) ───────────────────────
  hermes: {
    label: 'Hermes Engine',
    color: '#6366f1',
    bg: 'rgba(99,102,241,0.14)',
    svg: `<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
      <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="1.6"/>
      <path d="M8 8h8M8 12h5M8 16h8" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>
      <path d="M15 9l2 3-2 3" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>`
  },

  // ── vLLM (OpenAI-compatible inference server) ─────────────────────────
  vllm: {
    label: 'vLLM',
    color: '#f97316',
    bg: 'rgba(249,115,22,0.12)',
    svg: `<svg viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
      <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/>
    </svg>`
  },

  // ── LM Studio ─────────────────────────────────────────────────────────
  lmstudio: {
    label: 'LM Studio',
    color: '#a855f7',
    bg: 'rgba(168,85,247,0.12)',
    svg: `<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
      <circle cx="12" cy="12" r="9.5" stroke="currentColor" stroke-width="1.5"/>
      <circle cx="8.5" cy="10" r="2" fill="currentColor"/>
      <circle cx="15.5" cy="10" r="2" fill="currentColor"/>
      <circle cx="12" cy="15.5" r="1.5" fill="currentColor"/>
      <line x1="10.5" y1="10" x2="13.5" y2="10" stroke="currentColor" stroke-width="1.2"/>
      <line x1="9.3" y1="11.6" x2="11" y2="14" stroke="currentColor" stroke-width="1.2"/>
      <line x1="14.7" y1="11.6" x2="13" y2="14" stroke="currentColor" stroke-width="1.2"/>
    </svg>`
  },

  // ── HuggingFace Transformers (esecuzione nativa locale, tipo hf_local) ─
  transformers: {
    label: 'HF Transformers',
    color: '#fbbf24',
    bg: 'rgba(251,191,36,0.10)',
    svg: `<svg viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
      <path d="M9 3H5a2 2 0 0 0-2 2v4m6-6h10a2 2 0 0 1 2 2v4M9 3v18m0 0h10a2 2 0 0 0 2-2V9M9 21H5a2 2 0 0 1-2-2V9m0 0h18"/>
    </svg>`
  },

  unknown: {
    label: 'AI Model',
    color: '#8b5cf6',
    bg: 'rgba(139,92,246,0.12)',
    svg: `<svg viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
      <path d="M12 2a10 10 0 1 0 10 10A10 10 0 0 0 12 2zm0 18a8 8 0 1 1 8-8 8 8 0 0 1-8 8zm1-5h-2v-6h2zm0-8h-2V5h2z"/>
    </svg>`
  }
};

/**
 * Rileva il provider AI dal nome del modello.
 * @param {string} modelName - es. "mistralai/Mistral-7B-Instruct-v0.3"
 * @param {string} tipo - "hf_api" | "hf_local" | "local_url"
 * @returns {object} - entry di AI_PROVIDERS
 */
function detectProvider(modelName, tipo) {
  if (!modelName) return AI_PROVIDERS.unknown;
  const name = modelName.toLowerCase();

  // OpenAI
  if (name.includes('gpt-') || name.includes('openai') || name.includes('davinci') ||
      name.includes('text-embedding') || name.includes('whisper') || name.includes('dall-e')) {
    return AI_PROVIDERS.openai;
  }

  // Anthropic
  if (name.includes('claude') || name.includes('anthropic')) {
    return AI_PROVIDERS.anthropic;
  }

  // Meta / Llama
  if (name.includes('llama') || name.includes('meta-llama') || name.includes('codellama') ||
      name.includes('meta/') || name.includes('meta_llama')) {
    return AI_PROVIDERS.meta;
  }

  // Mistral
  if (name.includes('mistral') || name.includes('mixtral') || name.includes('mathstral') ||
      name.includes('pixtral')) {
    return AI_PROVIDERS.mistral;
  }

  // Google Gemma (prima di google generico)
  if (name.includes('gemma') || name.includes('codegemma') || name.includes('paligemma')) {
    return AI_PROVIDERS.gemma;
  }

  // Google / Gemini
  if (name.includes('gemini') || name.includes('google/') || name.includes('flan-t5') ||
      name.includes('bard') || name.includes('palm')) {
    return AI_PROVIDERS.google;
  }

  // Microsoft / Phi
  if (name.includes('phi-') || name.includes('microsoft/') || name.includes('orca') ||
      name.includes('wizardlm')) {
    return AI_PROVIDERS.microsoft;
  }

  // Cohere
  if (name.includes('cohere') || name.includes('command-r') || name.includes('c4ai')) {
    return AI_PROVIDERS.cohere;
  }

  // DeepSeek
  if (name.includes('deepseek')) {
    return AI_PROVIDERS.deepseek;
  }

  // Qwen / Alibaba
  if (name.includes('qwen') || name.includes('alibaba') || name.includes('tongyi')) {
    return AI_PROVIDERS.qwen;
  }

  // HuggingFace Transformers (tipo hf_local = esecuzione nativa)
  if (tipo === 'hf_local') {
    return AI_PROVIDERS.transformers;
  }

  // vLLM
  if (name.includes('vllm') || name.includes('vl-llm')) {
    return AI_PROVIDERS.vllm;
  }

  // LM Studio
  if (name.includes('lm-studio') || name.includes('lmstudio') || name.includes('lm studio')) {
    return AI_PROVIDERS.lmstudio;
  }

  // Ollama
  if (name.includes('ollama') || name.includes(':latest')) {
    return AI_PROVIDERS.ollama;
  }

  // Server locale generico con URL (es. local_url senza altri match)
  if (tipo === 'local_url') {
    return AI_PROVIDERS.local;
  }

  // HuggingFace generico (ha una slash = "org/model")
  if (name.includes('/')) {
    return AI_PROVIDERS.huggingface;
  }

  return AI_PROVIDERS.unknown;
}

/**
 * Restituisce l'HTML del logo per un dato provider.
 * @param {object} provider - entry di AI_PROVIDERS
 * @param {number} size - dimensione in px (default 28)
 */
function getProviderLogoHtml(provider, size = 28) {
  return `<span class="model-provider-logo" style="
    display:inline-flex;
    align-items:center;
    justify-content:center;
    width:${size}px;
    height:${size}px;
    border-radius:6px;
    background:${provider.bg};
    color:${provider.color};
    flex-shrink:0;
  ">${provider.svg}</span>`;
}

/**
 * Restituisce il badge pill del provider (logo + nome).
 */
function getProviderBadgeHtml(modelName, tipo) {
  const provider = detectProvider(modelName, tipo);
  const logoHtml = getProviderLogoHtml(provider, 22);
  return `<span class="provider-badge" style="
    display:inline-flex;
    align-items:center;
    gap:5px;
    padding:2px 8px 2px 4px;
    border-radius:20px;
    background:${provider.bg};
    color:${provider.color};
    font-size:11px;
    font-weight:600;
    letter-spacing:0.02em;
    border:1px solid ${provider.color}33;
  ">${logoHtml}<span>${provider.label}</span></span>`;
}

// ── Precaricamento SVG (warm-up al boot) ─────────────────────────────
// I logo sono SVG inline quindi non hanno latenza di rete,
// ma precarichiamo le definizioni in memoria al DOMContentLoaded.
(function preloadProviderLogos() {
  // Crea un container invisibile per "prerenderizzare" tutti i logo SVG
  const preloadContainer = document.createElement('div');
  preloadContainer.style.cssText = 'position:absolute;width:0;height:0;overflow:hidden;pointer-events:none;opacity:0;';
  preloadContainer.setAttribute('aria-hidden', 'true');
  preloadContainer.id = 'logo-preload-cache';

  const fragment = document.createDocumentFragment();
  for (const [key, provider] of Object.entries(AI_PROVIDERS)) {
    const wrapper = document.createElement('span');
    wrapper.innerHTML = provider.svg;
    wrapper.dataset.provider = key;
    fragment.appendChild(wrapper);
  }
  preloadContainer.appendChild(fragment);

  // Inserisce nel DOM subito dopo il caricamento
  if (document.body) {
    document.body.appendChild(preloadContainer);
  } else {
    document.addEventListener('DOMContentLoaded', () => {
      document.body.appendChild(preloadContainer);
    });
  }

  console.log(`[HERMES] Provider logos preloaded: ${Object.keys(AI_PROVIDERS).length} providers ready.`);
})();
