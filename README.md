# asass mod

Pacote portatil com fluxo 100% centralizado em um unico arquivo: `asass-mod.ps1`.

## Estrutura

- `asass-mod.ps1`: script unico com todas as funcionalidades
- `asass-mod.cmd`: atalho para abrir o menu
- `bin/`: executavel e bibliotecas Qt/SDL
- `bin/asass-mod.exe`: alias de executavel com branding
- `ps1/`: perfis `.amgp` para PS1/generic
- `ps3/`: perfis `.amgp` para PS3/gamepad compativel
- `themes/neo-carbon.qss`: tema visual

## Inicio rapido

1. Abra PowerShell na raiz do projeto.
2. Abra o menu unificado com comando curto:

```powershell
.\run.cmd
```

3. Alternativas de abertura:

```powershell
.\asass-mod.cmd
```

```powershell
powershell -ExecutionPolicy Bypass -File .\asass-mod.ps1 -Menu
```

## Comandos principais

### UI/UX e execucao

Abrir com tema:

```powershell
powershell -ExecutionPolicy Bypass -File .\asass-mod.ps1 -Run
```

Abrir modo vanilla:

```powershell
powershell -ExecutionPolicy Bypass -File .\asass-mod.ps1 -Vanilla
```

### Setup e auditoria

Setup portatil:

```powershell
powershell -ExecutionPolicy Bypass -File .\asass-mod.ps1 -Setup
```

Setup portatil com limpeza de referencias ausentes:

```powershell
powershell -ExecutionPolicy Bypass -File .\asass-mod.ps1 -Setup -CleanMissing
```

Auditoria e relatorio:

```powershell
powershell -ExecutionPolicy Bypass -File .\asass-mod.ps1 -Audit
```

Relatorio: `docs/settings-audit.md`

### Troca de perfil

Aplicar perfil em controladores ativos:

```powershell
powershell -ExecutionPolicy Bypass -File .\asass-mod.ps1 -SetProfile -ProfileName "mb.gamecontroller.amgp"
```

Forcar em todos os controladores:

```powershell
powershell -ExecutionPolicy Bypass -File .\asass-mod.ps1 -SetProfile -ProfileName "mb.gamecontroller.amgp" -AllControllers
```

### Backup

Gerar backup zip:

```powershell
powershell -ExecutionPolicy Bypass -File .\asass-mod.ps1 -Backup
```

Saida: `archives/asass-mod-pack-YYYYMMDD-HHMMSS.zip`

### Compile/recompile em arquivo unico

Compilar:

```powershell
powershell -ExecutionPolicy Bypass -File .\asass-mod.ps1 -BuildSingle
```

Recompilar:

```powershell
powershell -ExecutionPolicy Bypass -File .\asass-mod.ps1 -RebuildSingle
```

Saida: `dist/asass-mod-single.zip`

## Observacoes

- Tema dark real no codigo-fonte da UI exige build custom do projeto oficial AntiMicroX.
- O fluxo atual melhora visual via `-stylesheet` no binario existente.

## Troubleshooting

- Perfil nao carrega:
  - Rode `-Setup -CleanMissing` e depois `-Audit`
  - Verifique se o `.amgp` existe em `ps1/` ou `ps3/`
- AntiMicroX abre sem controles:
  - Reconecte o controle e abra o app novamente
  - Teste outra porta USB
