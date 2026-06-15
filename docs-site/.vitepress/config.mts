import { defineConfig } from 'vitepress'
import { withMermaid } from 'vitepress-plugin-mermaid'

export default withMermaid(defineConfig({
  title: 'OsuRender API',
  description: 'Production-grade, distributed osu! replay rendering service documentation',
  
  head: [
    ['meta', { name: 'theme-color', content: '#ff66aa' }],
    ['meta', { name: 'og:type', content: 'website' }],
    ['meta', { name: 'og:title', content: 'OsuRender API Documentation' }],
    ['meta', { name: 'og:description', content: 'Production-grade osu! replay rendering at scale' }],
    ['link', { rel: 'preconnect', href: 'https://fonts.googleapis.com' }],
    ['link', { rel: 'preconnect', href: 'https://fonts.gstatic.com', crossorigin: '' }],
    ['link', { href: 'https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;600&display=swap', rel: 'stylesheet' }],
  ],

  cleanUrls: true,
  lastUpdated: true,
  ignoreDeadLinks: [
    /^http:\/\/localhost/
  ],

  markdown: {
    lineNumbers: true,
    theme: {
      dark: 'one-dark-pro',
      light: 'github-light',
    },
  },

  themeConfig: {
    siteTitle: 'OsuRender API',
    
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
