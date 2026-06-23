import { defineConfig } from 'vitepress'
import { withMermaid } from 'vitepress-plugin-mermaid'

const SITE_URL = 'https://osu-render-api.vercel.app'
const OG_IMAGE = `${SITE_URL}/mascot3.png`
const SITE_TITLE = 'OsuRender API'
const SITE_DESCRIPTION = 'Production-grade, distributed osu! replay rendering service — GPU-accelerated, event-driven, and battle-tested at scale.'

export default withMermaid(defineConfig({
  title: SITE_TITLE,
  description: SITE_DESCRIPTION,
  
  head: [
    // — Charset & viewport —
    ['link', { rel: 'icon', type: 'image/png', href: '/mascot1.png' }],
    ['meta', { name: 'theme-color', content: '#ff66aa' }],
    ['meta', { name: 'author', content: 'Azaken' }],
    ['meta', { name: 'keywords', content: 'osu, osu!, replay, rendering, danser, api, gpu, modal, documentation' }],

    // — Open Graph —
    ['meta', { property: 'og:type', content: 'website' }],
    ['meta', { property: 'og:site_name', content: SITE_TITLE }],
    ['meta', { property: 'og:title', content: `${SITE_TITLE} — Documentation` }],
    ['meta', { property: 'og:description', content: SITE_DESCRIPTION }],
    ['meta', { property: 'og:image', content: OG_IMAGE }],
    ['meta', { property: 'og:image:width', content: '256' }],
    ['meta', { property: 'og:image:height', content: '256' }],
    ['meta', { property: 'og:image:type', content: 'image/png' }],
    ['meta', { property: 'og:url', content: SITE_URL }],
    ['meta', { property: 'og:locale', content: 'en_US' }],

    // — Twitter Card —
    ['meta', { name: 'twitter:card', content: 'summary_large_image' }],
    ['meta', { name: 'twitter:title', content: `${SITE_TITLE} — Documentation` }],
    ['meta', { name: 'twitter:description', content: SITE_DESCRIPTION }],
    ['meta', { name: 'twitter:image', content: OG_IMAGE }],

    // — Fonts —
    ['link', { rel: 'preconnect', href: 'https://fonts.googleapis.com' }],
    ['link', { rel: 'preconnect', href: 'https://fonts.gstatic.com', crossorigin: '' }],
    ['link', { href: 'https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;600&display=swap', rel: 'stylesheet' }],
  ],

  cleanUrls: true,
  lastUpdated: true,
  ignoreDeadLinks: [
    /^http:\/\/localhost/
  ],

  // Per-page OG tags derived from frontmatter
  transformPageData(pageData) {
    const pageTitle = pageData.frontmatter.title || pageData.title
    const pageDescription = pageData.frontmatter.description || pageData.description || SITE_DESCRIPTION
    const canonicalUrl = `${SITE_URL}/${pageData.relativePath}`
      .replace(/index\.md$/, '')
      .replace(/\.md$/, '')

    const ogImage = pageData.frontmatter.ogImage || OG_IMAGE

    pageData.frontmatter.head ??= []
    pageData.frontmatter.head.push(
      ['meta', { property: 'og:title', content: `${pageTitle} | ${SITE_TITLE}` }],
      ['meta', { property: 'og:description', content: pageDescription }],
      ['meta', { property: 'og:url', content: canonicalUrl }],
      ['meta', { property: 'og:image', content: ogImage }],
      ['meta', { name: 'twitter:title', content: `${pageTitle} | ${SITE_TITLE}` }],
      ['meta', { name: 'twitter:description', content: pageDescription }],
      ['meta', { name: 'twitter:image', content: ogImage }],
      ['link', { rel: 'canonical', href: canonicalUrl }],
    )
  },

  markdown: {
    lineNumbers: true,
    theme: {
      dark: 'one-dark-pro',
      light: 'github-light',
    },
  },

  themeConfig: {
    siteTitle: 'OsuRender API',
    logo: '/mascot1.png',
    
    nav: [
      { text: 'Guide', link: '/src/getting-started/introduction' },
      { text: 'API Reference', link: '/src/api-reference/overview' },
      { text: 'Architecture', link: '/src/architecture/system-overview' },
      {
        text: 'More',
        items: [
          { text: 'Deployment', link: '/src/deployment/docker-compose' },
          { text: 'Operations', link: '/src/operations/monitoring' },
          { text: 'Development', link: '/src/development/local-setup' },
          { text: 'Security', link: '/src/security/security-model' },
        ]
      },
      { text: 'GitHub', link: 'https://github.com/Azaken1248/OsuRenderApi' },
    ],

    sidebar: {
      '/src/getting-started/': [
        {
          text: 'Getting Started',
          items: [
            { text: 'Introduction', link: '/src/getting-started/introduction' },
            { text: 'Quick Start', link: '/src/getting-started/quick-start' },
            { text: 'Configuration', link: '/src/getting-started/configuration' },
          ]
        }
      ],
      '/src/api-reference/': [
        {
          text: 'API Reference',
          items: [
            { text: 'Overview', link: '/src/api-reference/overview' },
            { text: 'POST /v1/render', link: '/src/api-reference/render' },
            { text: 'Jobs API', link: '/src/api-reference/jobs' },
            { text: 'Skins API', link: '/src/api-reference/skins' },
            { text: 'Artifacts API', link: '/src/api-reference/artifacts' },
            { text: 'Webhook API', link: '/src/api-reference/webhook' },
            { text: 'Legacy Endpoints', link: '/src/api-reference/legacy' },
            { text: 'Error Codes', link: '/src/api-reference/error-codes' },
            { text: 'Rate Limiting', link: '/src/api-reference/rate-limiting' },
          ]
        }
      ],
      '/src/architecture/': [
        {
          text: 'Architecture',
          items: [
            { text: 'System Overview', link: '/src/architecture/system-overview' },
            { text: 'Data Flow & Lifecycle', link: '/src/architecture/data-flow' },
            { text: 'Transactional Outbox', link: '/src/architecture/outbox-pattern' },
            { text: 'Dispatcher Deep-Dive', link: '/src/architecture/dispatcher' },
            { text: 'Render Pipeline', link: '/src/architecture/render-pipeline' },
            { text: 'Database Schema', link: '/src/architecture/database-schema' },
            { text: 'ADRs', link: '/src/architecture/adrs' },
          ]
        }
      ],
      '/src/deployment/': [
        {
          text: 'Deployment',
          items: [
            { text: 'Docker Compose', link: '/src/deployment/docker-compose' },
            { text: 'Production', link: '/src/deployment/production' },
            { text: 'Modal GPU Workers', link: '/src/deployment/modal-gpu' },
            { text: 'Environment Variables', link: '/src/deployment/environment-variables' },
          ]
        }
      ],
      '/src/operations/': [
        {
          text: 'Operations',
          items: [
            { text: 'Monitoring & Alerting', link: '/src/operations/monitoring' },
            { text: 'Incident Runbooks', link: '/src/operations/runbooks' },
            { text: 'Dead Letter Queue', link: '/src/operations/dead-letter-queue' },
            { text: 'SLOs & SLIs', link: '/src/operations/slos' },
          ]
        }
      ],
      '/src/development/': [
        {
          text: 'Development',
          items: [
            { text: 'Local Setup', link: '/src/development/local-setup' },
            { text: 'Project Structure', link: '/src/development/project-structure' },
            { text: 'Testing Guide', link: '/src/development/testing' },
            { text: 'CI/CD Pipeline', link: '/src/development/ci-cd' },
            { text: 'Code Style', link: '/src/development/code-style' },
          ]
        }
      ],
      '/src/contributing/': [
        {
          text: 'Contributing',
          items: [
            { text: 'How to Contribute', link: '/src/contributing/how-to-contribute' },
            { text: 'Pull Request Process', link: '/src/contributing/pull-requests' },
            { text: 'Code of Conduct', link: '/src/contributing/code-of-conduct' },
          ]
        }
      ],
      '/src/security/': [
        {
          text: 'Security',
          items: [
            { text: 'Security Model', link: '/src/security/security-model' },
            { text: 'Threat Model', link: '/src/security/threat-model' },
            { text: 'Input Validation', link: '/src/security/input-validation' },
            { text: 'Reporting Vulnerabilities', link: '/src/security/reporting' },
          ]
        }
      ],
      '/src/roadmap/': [
        {
          text: 'Roadmap',
          items: [
            { text: 'Roadmap', link: '/src/roadmap/roadmap' },
          ]
        }
      ],
    },

    socialLinks: [
      { icon: 'github', link: 'https://github.com/Azaken1248/OsuRenderApi' },
    ],

    search: {
      provider: 'local',
    },

    editLink: {
      pattern: 'https://github.com/Azaken1248/OsuRenderApi/edit/main/docs-site/:path',
      text: 'Edit this page on GitHub',
    },

    footer: {
      message: 'Built with VitePress',
      copyright: '© 2026 OsuRender API',
    },

    outline: {
      level: [2, 3],
    },
  },
}))
