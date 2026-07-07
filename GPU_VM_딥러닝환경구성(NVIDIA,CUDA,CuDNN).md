
# GPU VM 딥러닝 환경 구성 (NVIDIA/CUDA/cuDNN/Tensorflow)


## 개요 
- GPU를 사용하는 VM에서 GPU를 통해 딥러닝 환경을 사용가능하도록 드라이버를 설치하는 방법을 정리 

### GPU 딥러닝 환경 구성 요소 

1. NVIDIA Driver
    - OS가 GPU를 인식하고 사용할 수 있도록 해주는 커널 모듈 및 유틸리티
        - CUDA도 이 위에서 동작함 
    - 설치된 CUDA Toolkit이 요구하는 최소 드라이버 버전 이상이어야 함
        - EX) CUDA 12.4 → NVIDIA Driver ≥ 550.40.07

2. CUDA Toolkit
    - GPU 코드 컴파일 (nvcc), 실행 환경 제공 (libcudart, cuBLAS 등)
    - TensorFlow/PyTorch 등이 GPU 연산을 이 위에 얹어서 사용
    - 딥러닝 프레임워크가 GPU 연산을 실제로 호출하기 위해 필요
    - TensorFlow/PyTorch 등 프레임워크에서 요구하는 정확한 버전 필요
        - EX) TensorFlow 2.13 → CUDA 11.8

3. cuDNN
    - CNN, RNN, LSTM 등의 연산을 최적화하여 빠르게 실행
    - CUDA 라이브러리를 보완하는 고성능 연산 모듈
    - TensorFlow, PyTorch가 GPU를 효율적으로 활용하도록 보조하는 역할 
    - 설치된 CUDA 버전과 정확히 맞는 cuDNN 버전 필요
        - EX) CUDA 11.8 → cuDNN 8.6.x


4. TensorFlow (GPU)
    - 딥러닝 모델의 구축, 학습, 추론을 담당
    - 내부적으로 CUDA/cuDNN 사용
    - 사용자가 직접 모델을 만들고 학습 및 추론하기 위해 필요
    - TensorFlow 버전 ↔ CUDA / cuDNN 버전 정확히 일치해야 함
        - EX)

            | TensorFlow 버전 | CUDA 버전 | cuDNN 버전 |
            |------------------|------------|--------------|
            | 2.13.x           | 11.8       | 8.6          |
            | 2.15.x           | 11.8       | 8.6          |
            | 2.16+            | 12.x       | 9.x 이상     |


### 전체 구성 요소 요약 

| 구성 요소                | 기능 및 역할                                        | 설치 이유                             | 버전 호환 기준                                                                                                      |
| -------------------- | ---------------------------------------------- | --------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| **NVIDIA Driver**    | OS가 GPU를 인식하고 사용할 수 있도록 해주는 커널 모듈 및 유틸리티       | GPU 사용 가능하게 함                     | - GPU 모델에 맞는 최신 안정 버전 <br>- CUDA Toolkit과 호환 필수                                                               |
| **CUDA Toolkit**     | GPU에서 병렬 연산을 수행하는 NVIDIA의 플랫폼 (컴파일러, 라이브러리 포함) | 딥러닝 프레임워크가 GPU를 통해 연산하도록 중간 계층 역할 | - TensorFlow 또는 PyTorch에서 요구하는 CUDA 버전 <br>🔍 [TF 공식 호환표](https://www.tensorflow.org/install/source#gpu) 참고   |
| **cuDNN**            | CNN, RNN 등 딥러닝 연산에 특화된 고성능 라이브러리 (CUDA 위에서 동작) | 딥러닝 연산을 효율적으로 실행 (속도/성능 개선)       | - CUDA Toolkit 버전에 맞는 cuDNN 버전 필요 <br>🔍 [cuDNN Release Note](https://docs.nvidia.com/deeplearning/cudnn/) 참고 |
| **TensorFlow (GPU)** | 딥러닝 프레임워크. CUDA/cuDNN을 통해 GPU 사용               | 딥러닝 모델 구현, 학습, 추론 수행              | - 설치된 CUDA/cuDNN 버전과 호환되는 버전만 사용 가능                                                                           |


### 각 구성 요소별 버전 체크 방법 

1. 사용할 TensorFlow 버전을 선택
2. TensorFlow 공식 GPU 지원 표에서 필요한 CUDA / cuDNN 버전 확인
3. 해당 CUDA가 요구하는 최소 NVIDIA Driver 버전 확인 후 설치
4. cuDNN은 NVIDIA 개발자 사이트에서 CUDA 버전에 맞춰 다운로드


<br>

---

<br>


## GPU 딥러닝 환경 구성 테스트 
- 실제 GPU를 사용하는 VM 상에서 GPU를 사용하는 딥러닝 환경 구성

### 구성 환경 
- 테스트 진행 환경 
    |Platform|OS|Machine_Type|GPU|
    |:-:|:-:|:-:|:-:|
    |GCP|Ubntu 20.04|n1-Stanadard-4|Nvidia T4 x1||


- 각 구성 요소 별 설치 버전 정보
    
    |구성요소|버전|비고|
    |:-:|:-:|:-:|
    |Python|3.12.11||
    |NVIDIA Driver|550.90.07|Run파일 실행|
    |CUDA Toolkit|12.4|Run파일 실행|
    |CuDNN|8.9.7|Nvidia 페이지 로그인 필요|
    |Tensorflow|2.19.0|Conda 가상환경 내 설치|




### NVIDIA Driver 550.90.07 설치 
 - [NVIDIA 드라이버 다운로드 ](https://www.nvidia.com/en-us/drivers) 에서  OS를 Linux 64-bit로 선택하면 Run파일 다운로드 가능
 - 버전 확인 후 링크 복사하여 wget으로 다운로드 
```
wget https://us.download.nvidia.com/XFree86/Linux-x86_64/550.90.07/NVIDIA-Linux-x86_64-550.90.07.run
chmod +x NVIDIA-Linux-x86_64-550.90.07.run
./NVIDIA-Linux-x86_64-550.90.07.run
```
- nvidia-smi 명령으로 정상 설치 확인 
```
nvidia-smi
```

###  Cuda Toolkit 12.4 설치 
- [Cuda Toolkit 아카이브](https://developer.nvidia.com/cuda-toolkit-archive) 에서 원하는 버전 다운로드 후 설치 
```
wget https://developer.download.nvidia.com/compute/cuda/12.4.0/local_installers/cuda_12.4.0_550.54.14_linux.run
./cuda_12.4.0_550.54.14_linux.run
```

- 설치 후 환경 변수 추가
```
echo 'export PATH=/usr/local/cuda/bin:$PATH' >> ~/.bashrc
echo 'export LD_LIBRARY_PATH=/usr/local/cuda/lib64:$LD_LIBRARY_PATH' >> ~/.bashrc
source ~/.bashrc
```

- 다른 계정에서도 사용가능하도록 권한 조정 
```
chmod -R a+rX /usr/local/cuda-12.4
chmod -R a+rX /usr/local/cuda
```

- nvcc명령어로 버전 확인 
```
nvcc --version
```

### cuDNN 8.9.7 설치 

- [cuDNN Archive](https://developer.nvidia.com/rdp/cudnn-archive) 에서 버전 선택 후 설치 
    - 링크 복사후 wget 안되므로 ftp으로 업로드 필요

```
tar -xvf cudnn-linux-x86_64-8.9.7.29_cuda12-archive.tar.xz
cd cudnn-linux-x86_64-8.9.7.29_cuda12-archive

cp include/cudnn*.h /usr/local/cuda/include/
cp lib/libcudnn* /usr/local/cuda/lib64/
chmod a+r /usr/local/cuda/include/cudnn*.h /usr/local/cuda/lib64/libcudnn*
```

### Conda(Miniconda) 설치
```
# 다운로드 (예: Linux x86_64, Python 3.10 기준)
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh

# 설치 ( 설치 중 Conda를 PATH에 추가하겠냐는 질문에 yes)
bash Miniconda3-latest-Linux-x86_64.sh

# 설치 후 환경 적용
source ~/.bashrc
```
### 신규 Conda 가상환경 구성 및 Tensorflow 설치 

- 신규 conda 가상환경 구성 및 활성화
```
conda create -n gpu-test python=3.12 -y
conda activate gpu-test
```

- Tensorflow 설치 
    - GPU 지원 버전 설치 시,  pip로 설치 필요
```
# pip 최신화
python -m pip install --upgrade pip setuptools wheel

# tensorflow 설치 
pip install tensorflow==2.19.0
```

### Tensorflow GPU 인식 테스트
```
python -c "import tensorflow as tf; print(tf.__version__); print(tf.config.list_physical_devices('GPU'))"

# 정상 인식 시
[PhysicalDevice(name='/physical_device:GPU:0', device_type='GPU')]
```