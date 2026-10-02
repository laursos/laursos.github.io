/* <image-slot> ligero: muestra la imagen indicada en src, a tamaño completo y recortada (cover).
   Sustituye al componente de edición original, que capturaba toques y teclado en móvil. */
(function(){
  if (customElements.get('image-slot')) return;
  class ImageSlot extends HTMLElement{
    static get observedAttributes(){return ['src','alt','placeholder'];}
    connectedCallback(){const st=this.style;if(!st.display)st.display='block';if(!st.width)st.width='100%';if(!st.height)st.height='100%';this.render();}
    attributeChangedCallback(){this.render();}
    render(){
      const src=this.getAttribute('src');
      let img=this.querySelector('img');
      if(!src){ if(img) img.remove(); this.style.background='var(--lm-green-tint,#E8F5EF)'; return; }
      if(!img){img=document.createElement('img');img.decoding='async';img.loading='lazy';
        img.style.cssText='width:100%;height:100%;object-fit:cover;display:block';this.appendChild(img);}
      img.alt=this.getAttribute('alt')||'';
      if(img.getAttribute('src')!==src) img.src=src;
    }
  }
  customElements.define('image-slot',ImageSlot);
})();
