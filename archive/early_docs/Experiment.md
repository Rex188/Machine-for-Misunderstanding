
VCV + Visualizer

---
我现在要project设计一个用于实验的blind test网页系统，用于测试人类语言通过一个music media之后产生的misunderstanding，用于展示现代社会交流的缺失和偏离，同时展示音乐作为语言媒介的魅力。

实验人员
参与实验的人有两个人，一方为输入，一方为接收，然后每轮实验两者身份互换。

实验流程
1. 输入方输入自己的text_input（心情，现象学感受），同时输入自己认为的vadc_input

2. 这个text_input传入到模型里，模型解读出vadc_model

3. vadc_model会被分为能够控制vcv的parameters

4. parameters 传输到 vcv 里，生成generative music

5. 接收方听到音乐之后给出他认为的vadc_receiver

6. 输入，接收方互换并重复上述步骤直到对话进行三轮（各输入一次算作一轮对话）

数据处理和计算

数据记录
每轮的text_input, vadc_input, vadc_model, parameters, vadc_receiver要写入一个json或者csv（log文件）
同时要保留每轮generative music的切片

数据处理
针对vadc_input, vadc_model, vadc_receiver做量化的计算，来测算所谓的“misunderstanding”

请根据我的设计找出不合理的地方




2 people on a stage

me - other 

me
1. text input
2. vadc1 input

> *text*: I'm very tired..
> VADC: 0.45, 

---

computer - vadc* - audio

---
other - audio
1. vadc2 input



same text, same audio - vadc1 / 2 - quantized

vadc* 

---

Outcome

---

***Blind test system*** + design the outcome, algorithm after getting the data.

---
