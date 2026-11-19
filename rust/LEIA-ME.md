# Redes para macOS

Redes é um aplicativo nativo para mapeamento científico (temas, autores, países e referências de um corpus). Funciona em Macs com chip Intel ou Apple Silicon, macOS 11 ou mais recente. Tudo é calculado na sua máquina.

## Instalar

1. Baixe `Redes-<versão>.dmg` na página de [Releases](../../../releases) do repositório.
2. Abra o `.dmg` e arraste **Redes** para a pasta **Aplicativos**.
3. Ejete o disco.

## Abrir pela primeira vez (app não assinado)

O Redes tem assinatura *ad hoc* (feita sem conta de desenvolvedor Apple) e não é notarizado. Por isso o macOS avisa que não consegue verificar o app na primeira abertura. O aviso aparece uma vez só.

**macOS 11 a 14:** na pasta Aplicativos, clique com o **botão direito** (ou Control + clique) em **Redes**, escolha **Abrir** e, na janela de aviso, clique em **Abrir**.

**macOS 15 (Sequoia) ou mais recente:** o clique com o botão direito não basta. Tente abrir o Redes normalmente, feche o aviso, vá em **Ajustes do Sistema > Privacidade e Segurança**, role até a mensagem sobre o Redes e clique em **Abrir mesmo assim**. Confirme com a senha ou o Touch ID.

### Alternativa pelo Terminal: remover a quarentena

O aviso vem do atributo de quarentena que o macOS põe em arquivos baixados. Para removê-lo:

```sh
xattr -dr com.apple.quarantine /Applications/Redes.app
```

Depois disso o app abre com duplo clique.

## Conferir o download (opcional)

Cada release traz o arquivo `Redes-<versão>.dmg.sha256` e a soma SHA-256 nas notas. Para conferir:

```sh
cd ~/Downloads
shasum -a 256 -c Redes-0.2.0.dmg.sha256
```

A saída deve ser `Redes-0.2.0.dmg: OK`.

## Usar

- **Importar corpus:** na tela inicial, escolha o arquivo exportado da base (ou arraste-o para a janela), dê um nome, indique o formato e, se quiser, os períodos (por exemplo `2011-2016, 2017-2019`). A importação mostra o andamento e pode ser cancelada. Nesta versão o importador ainda é uma simulação; para analisar dados reais, abra um projeto `.redes`.
- **Abrir projeto:** `.redes` pelo botão ou arrastando o arquivo para a janela.
- **Rede e diagrama estratégico:** a roda do mouse ou o gesto de pinça amplia e reduz em torno do cursor; arrastar move; no trackpad, dois dedos movem. Os botões **−**, **+** e **Ajustar** (teclas `-`, `+` e `0`) fazem o mesmo. Passe o mouse sobre um tema ou item para ver detalhes; clique num tema para abrir o painel lateral com seus itens e documentos; duplo clique enquadra o tema. Com muitos agrupamentos, os nomes aparecem conforme o zoom, sem se sobrepor.
- **Exportar:** botões SVG e PNG acima do gráfico.
- Abas **Dendrograma, Linha do tempo, Densidade, Similitude, Duplo mapa, Sankey** e **Relatório** aparecem esmaecidas ("Em breve") e serão ligadas nas próximas versões.

## Compilar e publicar

Requisitos: Rust estável e, no macOS, `brew install librsvg create-dmg`.

```sh
cd rust
cargo test -p redes-app
scripts/empacotar_mac.sh          # dist/Redes.app, dist/Redes-<versão>.dmg e .sha256
SO_UM_ALVO=1 scripts/empacotar_mac.sh   # só a arquitetura desta máquina (mais rápido)
```

`VERSAO=0.2.1 scripts/empacotar_mac.sh` sobrescreve a versão do `Cargo.toml` no nome do `.dmg` e no `Info.plist`.

O workflow `.github/workflows/mac.yml` roda a cada push em `rust-mac` e guarda o `.dmg` como artefato. Para **publicar um Release** (com o `.dmg` e o `.sha256`):

- crie e envie uma tag: `git tag v0.2.0 && git push origin v0.2.0`; ou
- na aba Actions, execute **Redes para macOS** manualmente e preencha o campo `versao` (ex.: `0.2.0`). Versões com sufixo (`0.3.0-rc1`) saem marcadas como pré-lançamento.

Se o Release da versão já existir, os arquivos são substituídos.

## Atalhos de desenvolvimento

Variáveis de ambiente para abrir o app direto em um estado (úteis em capturas de tela e testes):

`REDES_DEMO=1` (dados fictícios; só com `--no-default-features`), `REDES_DEMO_GRUPOS=120`, `REDES_ARQUIVO=<projeto.redes>`, `REDES_TELA=importar`, `REDES_ABA=rede|estrategico|…`, `REDES_SELECIONAR=<n>`, `REDES_ZOOM=<fator>`.

---

Criado por Gerlan Silva da Silva, doutorando em Educação (UFSCar).
