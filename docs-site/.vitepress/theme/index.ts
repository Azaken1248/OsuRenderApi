import DefaultTheme from 'vitepress/theme'
import './custom.css'
import { onMounted } from 'vue'

export default {
  ...DefaultTheme,
  setup() {
    onMounted(async () => {
      const svgPanZoomModule = await import('svg-pan-zoom');
      const svgPanZoom = (svgPanZoomModule as any).default || svgPanZoomModule;

      const hammerModule = await import('hammerjs');
      const Hammer = (hammerModule as any).default || hammerModule;

      const eventsHandler: any = {
        haltEventListeners: ['touchstart', 'touchend', 'touchmove', 'touchleave', 'touchcancel'],
        init: function(options: any) {
          var instance = options.instance
            , initialScale = 1
            , pannedX = 0
            , pannedY = 0;

          this.hammer = Hammer(options.svgElement, {
            recognizers: [
              [Hammer.Pinch, { enable: true }],
              [Hammer.Pan, { direction: Hammer.DIRECTION_ALL }]
            ]
          });

          this.hammer.on('panstart panmove', function(ev: any){
            if (ev.type === 'panstart') {
              pannedX = 0;
              pannedY = 0;
            }
            instance.panBy({x: ev.deltaX - pannedX, y: ev.deltaY - pannedY});
            pannedX = ev.deltaX;
            pannedY = ev.deltaY;
          });

          this.hammer.on('pinchstart pinchmove', function(ev: any){
            if (ev.type === 'pinchstart') {
              initialScale = instance.getZoom();
              instance.zoomAtPoint(initialScale * ev.scale, {x: ev.center.x, y: ev.center.y});
            } else {
              instance.zoomAtPoint(initialScale * ev.scale, {x: ev.center.x, y: ev.center.y});
            }
          });

          options.svgElement.addEventListener('touchmove', function(e: any){ e.preventDefault(); }, {passive: false});
        },
        destroy: function(){
          this.hammer.destroy();
        }
      };

      document.body.addEventListener('click', (e) => {
        const target = e.target as HTMLElement;

        // Handle closing the overlay
        const overlay = target.closest('.mermaid-fullscreen-overlay') as HTMLElement;
        if (overlay) {
          // Don't close if clicking pan/zoom controls
          if (target.closest('#svg-pan-zoom-controls') || target.tagName === 'path') return;
          
          if ((overlay as any).panZoom) {
            (overlay as any).panZoom.destroy();
          }
          overlay.remove();
          document.body.style.overflow = '';
          return;
        }

        // Handle clicking a mermaid diagram
        const mermaidContainer = target.closest('.mermaid') as HTMLElement;
        if (mermaidContainer) {
          const svg = mermaidContainer.querySelector('svg');
          if (!svg) return;

          // Create a fullscreen container overlay
          const newOverlay = document.createElement('div');
          newOverlay.className = 'mermaid-fullscreen-overlay';
          
          // Clone the SVG so we don't mutate the original document
          const clonedSvg = svg.cloneNode(true) as SVGSVGElement;
          clonedSvg.style.cssText = 'max-width: none !important; max-height: none !important; width: 100vw !important; height: 100vh !important; pointer-events: all;';
          
          newOverlay.appendChild(clonedSvg);
          document.body.appendChild(newOverlay);
          document.body.style.overflow = 'hidden';

          // Initialize panZoom on the cloned SVG
          setTimeout(() => {
            (newOverlay as any).panZoom = svgPanZoom(clonedSvg, {
              zoomEnabled: true,
              controlIconsEnabled: true,
              fit: true,
              center: true,
              minZoom: 0.1,
              maxZoom: 20,
              customEventsHandler: eventsHandler
            });
          }, 50);
        }
      });
      
      const observer = new MutationObserver(() => {
        document.querySelectorAll('.mermaid:not(.mermaid-wrapper)').forEach(el => {
          el.classList.add('mermaid-wrapper');
        });
      });
      observer.observe(document.body, { childList: true, subtree: true });
    })
  }
}
