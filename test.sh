pytest -v -s -x $1
# kill the validator -- even on test fail
ps aux | grep solana >.tmp &&
PID=$(awk 'BEGIN{FS=" ";}{print $2}' .tmp | head -n 1) &&
kill $PID && 
rm .tmp
