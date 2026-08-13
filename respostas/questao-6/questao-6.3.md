
## Questão 6.3 — Explicação

**1. Como o baseline foi construído?**
Para cada mês a prever, calculei a média da quantidade vendida (`sum(quantity)`) nos **3 meses imediatamente anteriores**. Não é uma média fixa recalculada uma vez só — é recalculada mês a mês, "andando" junto com o calendário (walk-forward): a janela desliza a cada novo mês previsto.

**2. Como evitei data leakage?**
Duas garantias: (1) para prever o mês M, uso só meses estritamente anteriores a M — nunca dados do próprio mês M ou de meses futuros; (2) ao prever fevereiro/2026, uso o valor **real** de janeiro/2026 (não uma previsão minha) — isso é válido porque, na operação real, quando chega a hora de planejar fevereiro, janeiro já aconteceu e o valor real já é conhecido. Isso evita o erro clássico de "vazar" informação do futuro, mas também evita o erro oposto de encadear previsão sobre previsão (o que acumularia erro artificialmente).

**3. Limitação do modelo proposto:** ausência de componente sazonal, a média móvel simples não enxerga **sazonalidade** (efeito mês-do-ano). Ela só reflete o nível recente da série, então qualquer produto com pico previsível (verão, Natal, etc.) vai ser sistematicamente subestimado nos meses de alta e superestimado nos meses de baixa — que é exatamente o padrão observado aqui.



