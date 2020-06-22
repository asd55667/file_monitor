# run monitor
python monitor.py &> monitor.log &

# basic test
cp ../imgs/*.jpg ./

# duplicate name test
cp ../imgs/*.jpg ./
cp ../imgs/*.jpg ./
cp ../imgs/*.jpg ./


# batch test
cp ../imgs/batch/* ./

python test_monitor.py

# # clean
# rm -rf ../checked ../error ../unchecked ../risky ./__pycache__
# rm *.jpg *.log
