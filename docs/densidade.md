# Mapa de densidade

Código em `scimatpy/viz/densidade.py`. Aba **Densidade** (modo avançado), rota
`/api/densidade`, e seção no relatório. SVG próprio, sem JavaScript; mesmos
dados dão sempre o mesmo texto.

1. **Itens.** Os 150 mais frequentes da rede de co-ocorrência (a tela aceita de
   20 a 300). Não vale para acoplamento nem cocitação de documentos.
2. **Posições.** Layout de atração e repulsão do tipo VOS: minimiza
   Σ sᵢⱼ·dᵢⱼ² − c·Σ ln dᵢⱼ por descida com momento (600 iterações, semente
   fixa). A similaridade é a força da ligação dividida pela maior ligação entre
   os itens do mapa. Itens soltos têm o excesso de distância comprimido a 25%.
3. **Densidade.** Soma de núcleos gaussianos centrados nos itens, com peso
   igual à frequência. A largura do núcleo é a suavização (padrão 4, de 1 a 9)
   × 0,8% da largura do quadro. Normaliza-se pelo máximo e eleva-se a 0,8.
4. **Cor.** De branco (0) a amarelo (1). Áreas quentes são vizinhanças de itens
   frequentes e bem ligados.
5. **Rótulos.** Até 40, por ordem de frequência, sem sobreposição e inteiros
   dentro do quadro; nomes com mais de 26 caracteres são cortados (texto
   inteiro na dica).
