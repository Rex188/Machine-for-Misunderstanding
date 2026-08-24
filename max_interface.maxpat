{
	"patcher": {
		"fileversion": 1,
		"appversion": {
			"major": 9,
			"minor": 0,
			"revision": 9,
			"architecture": "x64",
			"modernui": 1
		},
		"classnamespace": "box",
		"rect": [
			30.0,
			96.0,
			761.0,
			977.0
		],
		"gridsize": [
			15.0,
			15.0
		],
		"boxes": [
			{
				"box": {
					"format": 6,
					"id": "obj-38",
					"maxclass": "flonum",
					"numinlets": 1,
					"numoutlets": 2,
					"outlettype": [
						"",
						"bang"
					],
					"parameter_enable": 0,
					"patching_rect": [
						360.0,
						378.5,
						50.0,
						22.0
					]
				}
			},
			{
				"box": {
					"format": 6,
					"id": "obj-36",
					"maxclass": "flonum",
					"numinlets": 1,
					"numoutlets": 2,
					"outlettype": [
						"",
						"bang"
					],
					"parameter_enable": 0,
					"patching_rect": [
						360.0,
						315.0,
						50.0,
						22.0
					]
				}
			},
			{
				"box": {
					"format": 6,
					"id": "obj-34",
					"maxclass": "flonum",
					"numinlets": 1,
					"numoutlets": 2,
					"outlettype": [
						"",
						"bang"
					],
					"parameter_enable": 0,
					"patching_rect": [
						360.0,
						255.0,
						50.0,
						22.0
					]
				}
			},
			{
				"box": {
					"format": 6,
					"id": "obj-33",
					"maxclass": "flonum",
					"numinlets": 1,
					"numoutlets": 2,
					"outlettype": [
						"",
						"bang"
					],
					"parameter_enable": 0,
					"patching_rect": [
						360.0,
						195.0,
						50.0,
						22.0
					]
				}
			},
			{
				"box": {
					"id": "obj-1",
					"maxclass": "comment",
					"numinlets": 1,
					"numoutlets": 0,
					"patching_rect": [
						30.0,
						20.0,
						275.0,
						23.0
					],
					"text": "① 输入 A 的身体描述 —— 解锁编辑,锁回点击发送"
				}
			},
			{
				"box": {
					"id": "obj-2",
					"maxclass": "message",
					"numinlets": 2,
					"numoutlets": 1,
					"outlettype": [
						""
					],
					"patching_rect": [
						30.0,
						55.0,
						260.0,
						25.0
					],
					"text": "我手心冒汗，想站起来走"
				}
			},
			{
				"box": {
					"id": "obj-3",
					"maxclass": "comment",
					"numinlets": 1,
					"numoutlets": 0,
					"patching_rect": [
						30.0,
						82.0,
						346.0,
						23.0
					],
					"text": "↑ 解锁点它改文字,回车;锁回点它 = 追加一段(下面按钮锁定可点)"
				}
			},
			{
				"box": {
					"id": "obj-4",
					"maxclass": "message",
					"numinlets": 2,
					"numoutlets": 1,
					"outlettype": [
						""
					],
					"patching_rect": [
						30.0,
						120.0,
						296.0,
						25.0
					],
					"text": "我感觉很热，然后很闷，天气非常燥热，但是还能接受"
				}
			},
			{
				"box": {
					"id": "obj-5",
					"maxclass": "message",
					"numinlets": 2,
					"numoutlets": 1,
					"outlettype": [
						""
					],
					"patching_rect": [
						30.0,
						150.0,
						320.0,
						25.0
					],
					"text": "突然就很凉快，然后我舒服得很，我希望听到很欢快的节奏"
				}
			},
			{
				"box": {
					"id": "obj-6",
					"maxclass": "message",
					"numinlets": 2,
					"numoutlets": 1,
					"outlettype": [
						""
					],
					"patching_rect": [
						30.0,
						180.0,
						284.0,
						25.0
					],
					"text": "我的身体往里缩，肩膀提起来，呼吸变浅，我不敢动"
				}
			},
			{
				"box": {
					"id": "obj-7",
					"maxclass": "comment",
					"numinlets": 1,
					"numoutlets": 0,
					"patching_rect": [
						30.0,
						210.0,
						200.0,
						23.0
					],
					"text": "↑ 预制文本（单击发送）"
				}
			},
			{
				"box": {
					"id": "obj-8",
					"maxclass": "newobj",
					"numinlets": 1,
					"numoutlets": 1,
					"outlettype": [
						""
					],
					"patching_rect": [
						30.0,
						245.0,
						110.0,
						22.0
					],
					"text": "prepend /text"
				}
			},
			{
				"box": {
					"id": "obj-9",
					"maxclass": "newobj",
					"numinlets": 1,
					"numoutlets": 0,
					"patching_rect": [
						30.0,
						280.0,
						180.0,
						22.0
					],
					"text": "udpsend 127.0.0.1 7100"
				}
			},
			{
				"box": {
					"id": "obj-10",
					"maxclass": "comment",
					"numinlets": 1,
					"numoutlets": 0,
					"patching_rect": [
						360.0,
						20.0,
						300.0,
						23.0
					],
					"text": "② 机器此刻的状态（Python 每 0.1s 广播）"
				}
			},
			{
				"box": {
					"id": "obj-11",
					"maxclass": "newobj",
					"numinlets": 1,
					"numoutlets": 1,
					"outlettype": [
						""
					],
					"patching_rect": [
						360.0,
						55.0,
						120.0,
						22.0
					],
					"text": "udpreceive 7200"
				}
			},
			{
				"box": {
					"id": "obj-12",
					"maxclass": "newobj",
					"numinlets": 2,
					"numoutlets": 2,
					"outlettype": [
						"",
						""
					],
					"patching_rect": [
						360.0,
						90.0,
						90.0,
						22.0
					],
					"text": "route /state"
				}
			},
			{
				"box": {
					"id": "obj-14",
					"maxclass": "newobj",
					"numinlets": 1,
					"numoutlets": 7,
					"outlettype": [
						"float",
						"float",
						"float",
						"float",
						"int",
						"int",
						"float"
					],
					"patching_rect": [
						360.0,
						125.0,
						140.0,
						22.0
					],
					"text": "unpack 0. 0. 0. 0. 0 0 0."
				}
			},
			{
				"box": {
					"id": "obj-19",
					"maxclass": "number",
					"numinlets": 1,
					"numoutlets": 2,
					"outlettype": [
						"",
						"bang"
					],
					"parameter_enable": 0,
					"patching_rect": [
						520.0,
						195.0,
						60.0,
						22.0
					]
				}
			},
			{
				"box": {
					"id": "obj-20",
					"maxclass": "number",
					"numinlets": 1,
					"numoutlets": 2,
					"outlettype": [
						"",
						"bang"
					],
					"parameter_enable": 0,
					"patching_rect": [
						520.0,
						255.0,
						60.0,
						22.0
					]
				}
			},
			{
				"box": {
					"id": "obj-21",
					"maxclass": "number",
					"numinlets": 1,
					"numoutlets": 2,
					"outlettype": [
						"",
						"bang"
					],
					"parameter_enable": 0,
					"patching_rect": [
						520.0,
						315.0,
						60.0,
						22.0
					]
				}
			},
			{
				"box": {
					"id": "obj-22",
					"maxclass": "comment",
					"numinlets": 1,
					"numoutlets": 0,
					"patching_rect": [
						360.0,
						165.0,
						110.0,
						23.0
					],
					"text": "valence 明暗"
				}
			},
			{
				"box": {
					"id": "obj-23",
					"maxclass": "comment",
					"numinlets": 1,
					"numoutlets": 0,
					"patching_rect": [
						360.0,
						225.0,
						110.0,
						23.0
					],
					"text": "arousal 能量"
				}
			},
			{
				"box": {
					"id": "obj-24",
					"maxclass": "comment",
					"numinlets": 1,
					"numoutlets": 0,
					"patching_rect": [
						360.0,
						285.0,
						110.0,
						23.0
					],
					"text": "dominance 稳定"
				}
			},
			{
				"box": {
					"id": "obj-25",
					"maxclass": "comment",
					"numinlets": 1,
					"numoutlets": 0,
					"patching_rect": [
						360.0,
						345.0,
						110.0,
						23.0
					],
					"text": "confidence 确信"
				}
			},
			{
				"box": {
					"id": "obj-26",
					"maxclass": "comment",
					"numinlets": 1,
					"numoutlets": 0,
					"patching_rect": [
						515.0,
						165.0,
						70.0,
						23.0
					],
					"text": "当前步"
				}
			},
			{
				"box": {
					"id": "obj-27",
					"maxclass": "comment",
					"numinlets": 1,
					"numoutlets": 0,
					"patching_rect": [
						520.0,
						225.0,
						70.0,
						23.0
					],
					"text": "总步数"
				}
			},
			{
				"box": {
					"id": "obj-28",
					"maxclass": "comment",
					"numinlets": 1,
					"numoutlets": 0,
					"patching_rect": [
						520.0,
						285.0,
						70.0,
						23.0
					],
					"text": "剩余秒"
				}
			},
			{
				"box": {
					"id": "obj-31",
					"maxclass": "comment",
					"numinlets": 1,
					"numoutlets": 0,
					"patching_rect": [
						20.0,
						526.8040941953659,
						480.0,
						23.0
					],
					"text": "桥：Max(7100)→Python→seq→声音→VCV(7001)；状态回传→7200"
				}
			}
		],
		"lines": [
			{
				"patchline": {
					"destination": [
						"obj-12",
						0
					],
					"source": [
						"obj-11",
						0
					]
				}
			},
			{
				"patchline": {
					"destination": [
						"obj-14",
						0
					],
					"source": [
						"obj-12",
						0
					]
				}
			},
			{
				"patchline": {
					"destination": [
						"obj-19",
						0
					],
					"order": 0,
					"source": [
						"obj-14",
						4
					]
				}
			},
			{
				"patchline": {
					"destination": [
						"obj-20",
						0
					],
					"source": [
						"obj-14",
						5
					]
				}
			},
			{
				"patchline": {
					"destination": [
						"obj-21",
						0
					],
					"source": [
						"obj-14",
						6
					]
				}
			},
			{
				"patchline": {
					"destination": [
						"obj-33",
						0
					],
					"source": [
						"obj-14",
						0
					]
				}
			},
			{
				"patchline": {
					"destination": [
						"obj-34",
						0
					],
					"source": [
						"obj-14",
						1
					]
				}
			},
			{
				"patchline": {
					"destination": [
						"obj-36",
						0
					],
					"source": [
						"obj-14",
						2
					]
				}
			},
			{
				"patchline": {
					"destination": [
						"obj-38",
						0
					],
					"source": [
						"obj-14",
						3
					]
				}
			},
			{
				"patchline": {
					"destination": [
						"obj-8",
						0
					],
					"order": 1,
					"source": [
						"obj-2",
						0
					]
				}
			},
			{
				"patchline": {
					"destination": [
						"obj-8",
						0
					],
					"order": 1,
					"source": [
						"obj-4",
						0
					]
				}
			},
			{
				"patchline": {
					"destination": [
						"obj-8",
						0
					],
					"order": 1,
					"source": [
						"obj-5",
						0
					]
				}
			},
			{
				"patchline": {
					"destination": [
						"obj-8",
						0
					],
					"order": 1,
					"source": [
						"obj-6",
						0
					]
				}
			},
			{
				"patchline": {
					"destination": [
						"obj-9",
						0
					],
					"source": [
						"obj-8",
						0
					]
				}
			}
		],
		"dependency_cache": [],
		"autosave": 0
	}
}
