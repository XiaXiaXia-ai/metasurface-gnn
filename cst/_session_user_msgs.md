### seq 8
C:\Users\Xia\Documents\trae_projects\run_cst\build_coding_array.py检查代码，检查仿真设置是否合理

### seq 144
边界距离通过在Background properties中设置；把改好的完整版本写到 D:\DSHNESS\GNN；步改 P、坐标定义（脚本里是中心对称 (m-9.5)P，AF 里是 (m+0.5)P，形状不受影响但相位参考不同

### seq 201
如何开放权限

### seq 274
运行，完成建模和仿真设置，我手动检查后再运行仿真

### seq 500
我只要 define farfield monitor: farfield (f=10)一个监视器就行了，多加监视器是否会增加仿真时间

### seq 534
那加上9.9 9.8 10.1 10.2的监视器。完善代码，运行，建模和设置结果我手动检查

### seq 568
后处理结果要导出farfield的3D远场（后续相关1D和2D是否可以通过3D计算得到）

### seq 607
继续

### seq 708
现在运行仿真

### seq 951
我重新更换了基板材料With Material 
     .Reset 
     .Name "material1"
     .Folder ""
     .Rho "0"
     .ThermalType "Normal"
     .ThermalConductivity "0"
     .SpecificHeat "0", "J/K/kg"
     .DynamicViscosity "0"
     .UseEmissivity "True"
     .Emissivity "0"
     .MetabolicRate "0.0"
     .VoxelConvection "0.0"
     .BloodFlow "0"
     .MechanicsType "Unused"
     .SolarRadiationAbsorptionType "Opaque"
     .Absorptance "0.0"
     .UseSemiTransparencyCalculator "False"
     .SolarRadTransmittance "0.0"
     .SolarRadReflectance "0.0"
     .SolarRadSpecimenThickness "0.0"
     .SolarRadRefractiveIndex "1.0"
     .SolarRadAbsorptionCoefficient "0.0"
     .IntrinsicCarrierDensityModel "none"
     .FrqType "all"
     .Type "Normal"
     .MaterialUnit "Frequency", "GHz"
     .MaterialUnit "Geometry", "mm"
     .MaterialUnit "Time", "ns"
     .MaterialUnit "Temperature", "K"
     .Epsilon "2.65"
     .Mu "1"
     .Sigma "0.0"
     .TanD "0.0013"
     .TanDFreq "0.0"
     .TanDGiven "True"
     .TanDModel "ConstTanD"
     .SetConstTanDStrategyEps "AutomaticOrder"
     .ConstTanDModelOrderEps "3"
     .DjordjevicSarkarUpperFreqEps "0"
     .SetElParametricConductivity "False"
     .ReferenceCoordSystem "Global"
     .CoordSystemType "Cartesian"
     .SigmaM "0"
     .TanDM "0.0"
     .TanDMFreq "0.0"
     .TanDMGiven "False"
     .TanDMModel "ConstTanD"
     .SetConstTanDStrategyMu "AutomaticOrder"
     .ConstTanDModelOrderMu "3"
     .DjordjevicSarkarUpperFreqMu "0"
     .SetMagParametricConductivity "False"
     .DispModelEps "None"
     .DispModelMu "None"
     .DispersiveFittingSchemeEps "Nth Order"
     .MaximalOrderNthModelFitEps "10"
     .ErrorLimitNthModelFitEps "0.1"
     .UseOnlyDataInSimFreqRangeNthModelEps "False"
     .DispersiveFittingSchemeMu "Nth Order"
     .MaximalOrderNthModelFitMu "10"
     .ErrorLimitNthModelFitMu "0.1"
     .UseOnlyDataInSimFreqRangeNthModelMu "False"
     .UseGeneralDispersionEps "False"
     .UseGeneralDispersionMu "False"
     .NLAnisotropy "False"
     .NLAStackingFactor "1"
     .NLADirectionX "1"
     .NLADirectionY "0"
     .NLADirectionZ "0"
     .DiffuseScatteringCoefficient "0"
     .Color "0", "1", "1" 
     .Wireframe "False" 
     .Reflection "False" 
     .Allowoutline "True" 
     .Transparentoutline "False" 
     .Transparency "0" 
     .Create
End With

### seq 999
暂停

### seq 1015
更新了半径

### seq 1069
180°相位换成r=2

### seq 1112
以一个2*2的为小单元，单元总数保持不变

### seq 1161
以2×2的为基准，总结，交付文档

### seq 1498
清理相关内存占用（应为刚才仿真2*2时警报内存占用80%），然后做对比实验看之前加的Background properties的distance对结果的影响，仿真时间和结果

### seq 1567
打开15mm的cst文件

### seq 1593
默认15mm

### seq 1629
补充。然后生成大量数据（先计划1000组），编码数据和结果数据分别存进不同的文件夹，注意要随时可以中断，做好进度记录

### seq 1702
注意，启动静默模式，不要让弹窗中断流程

### seq 1703
启动CST的静默模式

### seq 1822
查询进度

### seq 1866
暂停

### seq 1931
继续

### seq 1964
暂停

### seq 1998
继续

### seq 2024
暂停

### seq 2051
继续

### seq 2076
暂停

### seq 2115
只要结束仿真就行

### seq 2133
继续

### seq 2167
暂停

### seq 2193
继续

### seq 2234
暂停

### seq 2261
继续

### seq 2339
在跑两千组

### seq 2406
检查

### seq 2504
暂停

### seq 2553
继续

### seq 2578
暂停

### seq 2604
继续

### seq 2648
一共仿真了多少组数据

### seq 2668
之前不是还跑了1000组吗

### seq 2685
数据存储在哪里

### seq 2703
基板的厚度

### seq 2731
继续跑，在跑1000组，注意编码不要和之前的重合

### seq 2812
暂停

### seq 2838
继续

### seq 2864
暂停

### seq 2891
仿真16*16的数据1000组存在另一个数据文档中

### seq 2986
暂停

### seq 3028
继续

### seq 3054
继续跑16*16

### seq 3154
跑12*12的

### seq 3216
12*12的跑完1000组了吗

### seq 3261
检查

### seq 3391
跑10×10的1000组

### seq 3444
检查

### seq 3480
现在用更精细的网格验证我选择的两个单元的反射相位有没有问题

### seq 3604
打开r=4的cst文件，我来手动设置网格

### seq 3630
文件里面怎么没有端口和参考面设置？

### seq 3695
暂停阵列的仿真

### seq 3736
继续跑阵列

### seq 3767
停止

### seq 3792
@C:\Users\Xia\Documents\trae_projects\temp_20261111_01\reflect_ess_on_state.py 以该单元为编码1，以同地板，基板，但顶层为全金属的单元为0，建立10*10的阵列，其中每个小单元是由2*2的子单元构成，现建模和设置仿真，我检查后运行

### seq 3896
继续

### seq 3922
我现在换了Hexahedral TLM网格划分，你在帮我把金属顶片都布尔运算合并，看看这样的网格量

### seq 3971
还是适用HexahedralTLM。局部网格存在问题，把编码单元的顶层金属全部合并，然后局部网格细化，**Absolute value**为0.2

### seq 4082
TLM可以走通，我能手动勾选。检查下你的操作，局部细化也可以

### seq 4224
一个个合并太慢了，全部选中要合并的一起合并，或者把要合并的放在一个component下直接合并。

### seq 4289
停止，你现在也很慢，把要合并的东西建模的时候就放在一个component里，看能不能直接全选中划分网格，就不用合并了。建模也慢，以后再跑数据集的时候注意，替换不同的的单元，重新跑，不要从头开始建模了。或者通过平移复制金属片和离散器件也行

### seq 4337
继续，所有都是TLM网格，然后顶层的编码单元的金属结构选中局部网格细化，**Absolute value**为0.2

### seq 4725
调整直接2*2的小单元作为一个复制模块

### seq 4726
调整直接2*2的小单元作为一个复制模块

### seq 4774
将2*2的复制模块的金属顶层的部分先布尔运算合并了再复制

### seq 4815
将2*2的复制模块的金属顶层的部分先布尔运算合并了再复制

### seq 4841
用边缘细化。我的贴片单元距离外侧的金属边的距离是0.5mm

### seq 4889
1

### seq 4906
已完成

### seq 4939
看看是不是都细化，还是只有我选的单元细化了

### seq 4966
调节整体的网格可以吗

### seq 4985
你来改，重新来建模一次

### seq 5211
用默认的网格跑10*10（小单元，按大单元算是5*5)的阵列。用TLM的默认的网格划分。跑随机编码100组，然后是16*16，100组。注意检查仿真设置

### seq 5262
先暂停

### seq 5272
适当的细分网格
