# VCV Rack 跳线实操执行指南 (Patching Playbook)
## A Machine for Misunderstanding: 声音四要素与 Coordinator 跳线手册

> **适配工程**：`portfolio/project2/generative template.vcv`  
> **目标**：在现有 5 声部高阶生成工程基础上，接入 `cvOSCcv`，完成**声音四要素（Timbre, Frequency, Amplitude, Envelope）**以及**Coordinator（媒介协调器）**的物理跳线。  
> **归档位置**：`portfolio/project2/VCV_跳线实操指南.md`

---

## 阶段零：模块布局与准备

打开 `generative template.vcv`，当前机架共有 3 排（Row 0, Row 1, Row 2）。

### 1. 新增 1 个核心模块
* 在机架空白处（推荐放在 **Row 1 最左侧，即 `MM_Tools SHEight` 左边**，或 **Row 0 最左侧 `MixMaster` 上方/旁边**）右键添加：
  * **Brand**: `trowaSoft`
  * **Module**: `cvOSCcv`（8 通道 OSC ↔ CV 双向转换器）

---

## 阶段一：cvOSCcv 模块参数配置（红线步骤，防收不到信号）

右键点击或在 `cvOSCcv` 面板上配置：

1. **端口设置**：
   * **RxPort (接收端口)**：设为 **`7001`**（必须与 Python `seq_to_osc.py` 的默认输出端口一致）。
   * **TxPort (发送端口)**：默认 `7000`（不使用可忽略）。
   * **IP**：`127.0.0.1`。
2. **输出通道地址映射 (Output Channels Config)**：
    点击 `cvOSCcv` 面板的 `CH/CONFIG` 按钮，配置 8 个输出通道的 OSC 地址：
    * **CH 1**：Path = `/param/timbre`（Plaits Mode CV，0V ~ 2.4V）
    * **CH 2**：Path = `/param/frequency`（Clocked BPM CV，-3V ~ +4V）
    * **CH 3**：Path = `/param/amplitude`（VCA-1 增益，+2V ~ +10V，满载饱满）
    * **CH 4**：Path = `/param/envelope`（Plateau 空间残响，-5V ~ +5V）
    * **CH 5**：Path = `/param/mode`（ScaleCV 调式选择，-4V ~ +2V）
    * **CH 6**：Path = `/param/chord`（DiatonicCV 和弦级数，0V ~ 6V）
    * **CH 7**：Path = `/param/type`（DiatonicCV 和弦类型，0V ~ 2V）
    * **CH 8**：Path = `/param/noise`（MixMaster Track 5 噪声推子，+2V ~ +10V）

---

## 阶段二：声音核心跳线矩阵（逐根执行）

> 💡 **跳线原则**：现有工程已有自己的自激走线，我们**不需要拔掉原有的核心音频线**，只需将 `cvOSCcv` 的 CV 信号插入对应模块的 **CV 调制孔（CV In）** 即可。

```text
┌──────────────┐ CH 1 (/param/timbre)     ┌────────────────────────┐
│              │─────────────────────────>│ Plaits [In 0: MODE CV] │ (0V正弦 ~ 0.66V FM金属 ~ 2.1V和弦)
│              │                          └────────────────────────┘
│              │ CH 2 (/param/frequency)  ┌────────────────────────┐
│              │─────────────────────────>│ Clocked [In 6: BPM]    │ (50 ~ 220+ BPM)
│              │                          └────────────────────────┘
│              │ CH 3 (/param/amplitude)  ┌────────────────────────┐
│   cvOSCcv    │─────────────────────────>│ VCA-1 [CV Level In]    │ (2V底限 ~ 10V爆响)
│  (Rx: 7001)  │                          └────────────────────────┘
│              │ CH 4 (/param/envelope)   ┌────────────────────────┐
│              │─────────────────────────>│ Plateau [Decay/Wet]    │ (空间残响弥散)
│              │                          └────────────────────────┘
│              │ CH 5 (/param/mode)       ┌────────────────────────┐
│              │─────────────────────────>│ ScaleCV [In 1: MODE]   │ (-2V Phrygian ~ -4V Major)
│              │                          └────────────────────────┘
│              │ CH 6 & 7 (chord / type)  ┌────────────────────────┐
│              │─────────────────────────>│ DiatonicCV [CHORD/TYPE]│ (I~VII级 & 三/七/九和弦)
│              │                          └────────────────────────┘
│              │ CH 8 (/param/noise)      ┌────────────────────────┐
│              │─────────────────────────>│ MixMaster [Track 5 CV] │ (2V底噪 ~ 10V蒸汽海啸)
└──────────────┘                          └────────────────────────┘
```

### 关键架构决策：Arp 解耦与 Const Add 偏置
* **为什么加 Const Add**：
  为避免 Arp 和弦与 Plaits 的 Mode 切换发生频段冲突，在 `DiatonicCV` 到 `HamptonHarmonics Arp` 的音高输入之间串入一个 **Const Add（如 `Bogaudio OFFSET` 或 `Fundamental 8vert`）**：
  * 设置直流偏置为 **`+1.0V` 或 `+2.0V`**（即强制上移 1~2 个八度）；
  * **效果**：Plaits 负责中低频的合成器质变，Arp 稳稳悬浮在清脆的高频晶莹区域，两个声部层次完全拉开！

### 1. 【Timbre 音色】跳线
* **目标模块**：Row 1, Col 6 的 **`AudibleInstruments Plaits` (Macro Oscillator 2)**
  * **线 ①**：从 `cvOSCcv` 的 **CH 1 输出孔** $\rightarrow$ 插到 Plaits 的 **`TIMBRE` CV 输入孔**（左侧输入列，第 2 个孔，In 1）。
  * **线 ②**（多路复用）：从 `cvOSCcv` 的 **CH 1 输出孔**（按住 Ctrl/Cmd 拖出第二根线，或过 Split）$\rightarrow$ 插到 Plaits 的 **`MORPH` CV 输入孔**（左侧输入列，第 4 个孔，In 3）。
* **辅助连动（低频厚度）**：
  * **线 ③**：从 `cvOSCcv` 的 **CH 1 输出孔** $\rightarrow$ 插到 Row 2, Col 23 的 **`Instruo io47`** 的 **`FREQ/CUTOFF CV`** 输入孔。

---

### 2. 【Frequency 频率与节奏型】跳线
* **目标模块**：Row 2, Col -38 的 **`ImpromptuModular Clocked`**
  * **线 ④**：从 `cvOSCcv` 的 **CH 2 输出孔** $\rightarrow$ 插到 Clocked 的 **`BPM` 输入孔**（右下角 Input 区，标记为 BPM 的孔，即 In 6）。
* **节奏型紧凑度连动**：
  * **线 ⑤**：从 `cvOSCcv` 的 **CH 2 输出孔** $\rightarrow$ 插到 Row 2, Col -8 的 **`CountModula Chances`** 的 **`PROB CV`（概率 CV）** 输入端。
  * *效果*：频率越高，不仅 BPM 变快，琶音器出声概率也从稀疏变致密。

---

### 3. 【Amplitude 振幅】跳线
* **目标模块**：Row 1, Col 71 的 **`Fundamental VCA-1`**（控制 Track 1 Pad 的主 VCA）及 Row 0 的 **`MixMaster`**
  * **线 ⑥**：从 `cvOSCcv` 的 **CH 3 输出孔** $\rightarrow$ 插到 Row 1, Col 71 的 **`VCA-1` 的 `CV` 输入孔**（上数第 2 个孔，Level CV）。
  * **线 ⑦**：从 `cvOSCcv` 的 **CH 3 输出孔** $\rightarrow$ 插到 Row 0 的 **`MindMeld MixMaster`** 的 **Track 1 / Track 2 Level CV 孔**（底部 CV 展开扩展孔）。

---

### 4. 【Envelope 包络】跳线
* **目标模块**：Row 2, Col 85 的 **`Fundamental ADSR`**
  * **线 ⑧**：从 `cvOSCcv` 的 **CH 4 输出孔** $\rightarrow$ 插到 ADSR 的 **`ATTACK` CV 输入孔**（左侧 In 0，若无直接 CV 孔，接入 Attack 衰减旋钮关联孔）。
  * **线 ⑨**：从 `cvOSCcv` 的 **CH 4 输出孔** $\rightarrow$ 插到 ADSR 的 **`RELEASE` CV 输入孔**（In 3）。
* **空间残响深度连动**：
  * **线 ⑩**：从 `cvOSCcv` 的 **CH 4 输出孔** $\rightarrow$ 插到 Row 0, Col 65 的 **`Valley Plateau`** 的 **`DECAY` 或 `WET` CV 输入孔**。
  * *效果*：包络越宽，混响尾迹越长，声音溶入虚无。

---

## 阶段三：Coordinator（媒介协调器）4 根画龙点睛跳线

这一阶段是让系统拥有“媒介阻抗与自主偏差”的关键！

```text
┌─────────────────────────┐
│ Vult Caudal (物理双摆)   │──(微量混入)──> Plaits [TIMBRE CV] (布朗漂移)
└─────────────────────────┘
┌─────────────────────────┐
│ cvOSCcv CH 3 (Amp冲击)  │──(高通/串扰)─> Instruo io47 [DRIVE] (信道破裂)
└─────────────────────────┘
┌─────────────────────────┐
│ CountModula Chances     │──(抽样阻断)──> ADSR Gate (记忆迟滞)
└─────────────────────────┘
```

### 1. 媒介物理漂移（Brownian Drift）
* **源模块**：Row 1, Col 101 的 **`Vult Caudal`**（混沌摆）
  * **线 ⑪**：从 `Caudal` 的 **`OUT 1`** $\rightarrow$ 插到 Row 1, Col 6 的 `Plaits` 的 **`TIMBRE CV` 衰减小旋钮**（微调旋钮至 15% 左右）。
  * *听感*：即使静止，音色也有缓慢的非周期性物理呼吸感。

### 2. 信道漏电串扰（Acoustic Cross-talk）
* **源模块**：`cvOSCcv` 的 **CH 3 (Amplitude)**
  * **线 ⑫**：从 `CH 3` 拖出一根线 $\rightarrow$ 插到 Row 2, Col 23 的 **`Instruo io47` 的 `DRIVE` 或 `RESONANCE` CV 输入孔**。
  * *听感*：当人说话特别用力、振幅冲到最高时，滤波器瞬间发生模拟电路过载破音。

### 3. 记忆迟滞与丢包（Hysteresis）
* **源模块**：Row 1, Col -38 的 **`MM_Tools SHEight`** + Row 1, Col 64 的 **`CountModula Chances`**
  * 将 `cvOSCcv` 的更新信号先过一次 `SHEight` 采样保持，再由 `Chances` 随机时钟触发抽样。
  * *听感*：新指令到达时，有 20% 几率“装作没听见”，卡在上一状态 3 秒后再更新。

---

## 阶段四：旋钮与安全底线校准 (Knob Positions & Headroom)

接好线后，请按以下基准校准核心旋钮，确保声音平衡且**绝不爆音**：

1. **`MindMeld MixMaster` 调音台**：
   * Master Fader 设在 **`-3.0 dB`** 位置。
   * 各轨已命名清晰标注：
     * Track 1: `PAD`（Fader: `-6.0 dB`）
     * Track 2: `ARP`（Fader: `-8.0 dB`，经由 Bogaudio-VCF 滤波）
     * Track 3: `BASS`（Fader: `-4.0 dB`，由 io47 塑形）
     * Track 4: `LEAD`（Fader: `-10.0 dB`，Basal + Wolv）
     * Track 5: `NOIS`（Fader: `-14.0 dB`，受 Caudal 混沌漂移驱动）
   * **声像（Pan）**：已全部接入 `Vult Caudal` 物理双摆输出（Out 0~3, 9），彻底消除单调的周期性摆动。
2. **Master 混音母带安全链路（MixMaster $\rightarrow$ Comp $\rightarrow$ Limiter $\rightarrow$ DAC）**：
   * `squinkylabs-comp`（母带总线压缩）：
     * `THRESHOLD`: **`-8.0 dB`**，`RATIO`: **`3:1`**，`ATTACK`: `25 ms`，`RELEASE`: `150 ms`。
   * `Bogaudio-Lmtr`（母带砖墙防削波限幅器）：
     * 挂载在声卡直接输入前端，`Threshold` 设为 **`-1.5 dB`**，软拐点保护，杜绝任何生成式瞬态过载爆音。
3. **`Valley Plateau` 空间混响（Aux 1 规范）**：
   * `DRY`: **`0.0` (Kill Dry 100% 全湿)**，消除发送总线带来的原声干信号叠加与梳状滤波。
   * `WET`: **`1.0`**，`DECAY`: **`0.88`**（12~15 秒缥缈扩散尾音），混响深度纯由 MixMaster Aux 1 发送量掌控。
4. **`AudibleInstruments Plaits`**（Row 1, Col 6）：
   * `TIMBRE` 衰减小旋钮顺时针开至 **`2 点钟方向 (+0.75)`**。
   * `MORPH` 衰减小旋钮顺时针开至 **`2 点钟方向 (+0.75)`**，使 Timbre CV 调制真实生效。
5. **`ImpromptuModular Clocked`**（Row 2, Col -38）：
   * 中间大旋钮 `BPM` 设为初始值 **`100 BPM`**。

---

## 阶段五：运行验证步骤

1. 启动你的 Python 驱动脚本：
   ```bash
   cd "/Users/rexli/Documents/Rex/portfolio/project2/workflow"
   python3 seq_to_osc.py --verbose
   ```
2. 观察 `cvOSCcv` 面板：
   * 面板上的绿色指示灯应随着 Python 发送的 10Hz 信号闪烁；
   * CH1 ~ CH4 的电压数值实时跳动。
3. 听觉测试：
   * 喂入第 1 段《金阁寺》文本（剧烈抽搐、口吃失控）：检查 BPM 是否加快、音色是否出现刺耳波形折叠破音；
   * 喂入第 2 段《春雪》文本（极度冰冷、下沉消融）：检查声音是否变暗、Plateau 混响尾迹是否漫天扩散；
   * 喂入第 3 段《喧哗与骚动》文本（火光、明亮奔涌）：检查琶音是否如潮水般涌出。
