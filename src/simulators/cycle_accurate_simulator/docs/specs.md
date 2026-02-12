# Specs

- Host AXI Lite Client
  => Registres de controles

| Registre | Type              | valeur à écrire |
| -------- | ----------------- | --------------- |
| 0        | instruction count | 5               |
| 12       | instructions      | 6000            |
| 16       | UOP               | 5000            |
| 20       | Input             | 1000            |
| 24       | Weights           | 2000            |
| 28       | Acc               | 3000            |
| 32       | Outputs           | 4000            |

- instructions
- UOP
- weights
- acc
- outputs

- 1 registres pour lancer l'éxecution

- 1 registre pour monitorer la complétion (à confirmer)

- Master Mem AXI Full:
  => écrire données dans les addresses correspondantes

# Fichiers

- données / instructions (initialisation DRAM):
  \*.bin
  ou dram_init.json

- sources à mettre dans une IP
