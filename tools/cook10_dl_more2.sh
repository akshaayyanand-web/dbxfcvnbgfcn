for p in XAGUSD UDXUSD EURAUD GBPAUD EURNZD GBPCAD CHFJPY NZDJPY EURCHF AUDNZD GBPCHF EURCAD; do
  for y in 2016 2017 2018 2019 2020 2021 2022 2023 2024 2025; do [ -s hd/raw/${p}_${y}.zip ] || timeout 300 python3 /home/user/dbxfcvnbgfcn/tools/histdata_get.py hd/raw $p $y 2>&1 | tail -1; sleep 3; done
  for m in 1 2 3 4 5 6 7 8 9 10; do mm=$(printf "%02d" $m); [ -s hd/raw/${p}_2026${mm}.zip ] || timeout 300 python3 /home/user/dbxfcvnbgfcn/tools/histdata_get.py hd/raw $p 2026 $m 2>&1 | tail -1; sleep 3; done
done
echo DONE
