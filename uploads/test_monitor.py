import cv2 
import numpy as np
import os

def write_sample_img(dst: str = '.'):   
    fixed_width = 1 << 10

    pair = [(1,1), (2,1), (2,2), (3,2), (3,3),(4,3)]
    for i, j in pair:
        arr =  np.random.randint(0, 255, (fixed_width << i, fixed_width << j))
        cv2.imwrite(f'{1 << (i + j)}M.jpg', arr)    

if __name__ == "__main__":
    write_sample_img()
    if platform.system()=='Windows':
        os.system("del -rf ../checked ../error ../unchecked ../risky ./__pycache__")
        os.system("del *.jpg *.log")        
    else platform.system()=='Linux':
        os.system("rm -rf ../checked ../error ../unchecked ../risky ./__pycache__")
        os.system("rm *.jpg *.log")
