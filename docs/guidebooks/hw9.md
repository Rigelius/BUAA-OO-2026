# 面向对象规格化设计系列第一次代码作业指导书

## 第零部分：提交要求

<font color=red>**请勿提交官方包代码，仅提交自己实现的类。更不要将官方包的 JML 或代码粘贴到自己的类中，否则可能以作弊、抄袭论处。**</font>

请保证提交项目的顶层目录至少存在两个文件夹：`src` 和 `test`（命名需严格与此保持一致），请将作业的**功能代码**文件存放于 `src` 文件夹下，同时将相关 Junit **测试代码**文件存放于 `test` 文件夹下，以保证评测的正常进行（评测时**只会**针对 `src` 目录下的文件进行**程序功能**的评测以及**代码风格**检测，也就是说，`test` 目录下的 Junit 测试代码风格**不会**被检测）。参考目录结构如下：

```
|-src
|  |- MainClass.java
|  |- User.java
|  |- Network.java
|  |- Video.java
|  |- ...
|-test
|  |- Test.java
|  |- ...
```

**注意**：为了通过 Junit 测试的编译，请大家实现课程组提供的接口时不要分包（在 src 下创建子目录），而是将所有实现接口的类都直接放在 src 目录下，否则本地运行正常的 Junit 测试类代码在评测机上会无法找到课程组提供的待测试类文件。

## 第一部分：训练目标

本次作业中，需要完成的任务为模拟网络社区（如哔哩哔哩）的用户关注关系网络及视频互动；学习目标为对规格化开发（以入门级 JML 规格为例）的理解与相应的代码实现。

## 第二部分：预备知识

需要同学们了解基本的 JML 语法和语义，以及具备根据 JML 给出的规格编写 Java 代码的能力。JML 教程可参考仓库内 JML Level 0 使用手册。

**注意**：为了简化代码，便于同学们阅读，我们对 JML 进行了一定程度的拓展。对于标注了 `safe` 的方法，只可以保证 JML 描述内容，可能有 side effect，伴随容器长度的增减或者对象的修改，但是不可以有如下的 side effect，具体体现为：

1. 不可在任何容器或对象中增加 JML 没有要求加入的对象。
2. 不可在任何容器或对象中删除 JML 没有要求删除的对象。
3. 不可对 JML 描述中涉及之外的对象或涉及对象中的非涉及属性进行内容的修改，即 JML 涉及之外的对象或属性的 object representation（对应二进制序列）应该前后一致。

## 第三部分：题目描述

### 一、作业基本要求

本次作业要求同学们维护一个视频网站的社交网络，并对其中的用户、视频以及他们之间的关注、互动关系进行管理。

- 社交网络的整体框架官方已经给出了 JML 表述并提供了相应接口。同学们需要**阅读 JML 规格，依据规格实现自己的类和方法。**

    具体来说，各位同学需要新建自己的 `User`、`Network`、`Video` 类，并分别实现官方包中提供的 `UserInterface`、`NetworkInterface`、`VideoInterface` 接口，最终类中每个方法的代码实现都需要**严格满足**接口中给出的 JML 规格定义。

- 阅读指导书中关于**异常**行为的描述，结合官方包中提供的异常类的 **javadoc**（或源码），体会异常处理的流程。

    异常类已在官方包内给出，这一部分**没有提供 JML 规格**，而是提供了一些相对标准的文档注释来向大家介绍类或方法的功能和参数的含义。各位同学需要仔细阅读指导书中关于异常类的详细描述，恰当地使用这些异常类，正确处理我们规定的各种异常情况，并保证所有的 print() 方法能够正确输出指定的信息。

此外，还需要同学们在**主类**中通过调用官方包的 `Runner` 类，并载入自己实现的 `User`、`Network`、`Video` 类，来使得程序完整可运行。

### 二、类规格要求

**注意**：
- 同学们需要保证实现 `NetworkInterface` 接口的类命名为 `Network`，实现 `UserInterface` 接口的类命名为 `User`，实现 `VideoInterface` 接口的类命名为 `Video`。
- JUnit 评测时，课程组提供的评测代码同样满足上述命名规则。

所有类的具体接口规格见官方包的代码，此处不加赘述。

请确保各个类的**构造方法**正确实现，且类和构造方法均定义为 `public`。`Runner` 内将自动获取**符合下方说明的**构造方法来构造各个类的实例。

#### User 类

**构造方法**，用以生成和初始化一个 User 对象：

```java
public class User implements UserInterface {
    public User(int id, String name, int age);
}
```

**属性**：

- `id`：在整个程序运行过程中的所有时刻，在当前 `Network` 中出现过的所有 `User` 对象中独一无二的 `id`
- `name`：姓名
- `age`：年龄

此外，`User` 内部还需要维护**属性容器**，如关注列表 `following`、粉丝列表 `followers`、接收到的视频列表 `receivedVideos` 等，具体表述参见 `UserInterface` 接口。

#### Network 类

**构造方法**，用以生成一个 Network 对象：

``` java
public class Network implements NetworkInterface {
    public Network();
}
```

此外，`Network` 内部还需要维护属性数组 `users` 和 `videos`，具体表述参见 `NetworkInterface` 接口。

#### Video 类

**构造方法**，用以生成一个 Video 对象：

``` java
public class Video implements VideoInterface {
    public Video(int id, int uploaderId);
}
```

**属性**：

- `id`：视频 ID
- `uploaderId`：上传者 ID

#### 异常类

本次作业的官方包中给出了 **9** 个异常类，同学们可以直接调用，官方包会捕获这些异常，并处理异常输出（具体逻辑见官方包中的 `Runner` 类）。

- `EqualUserIdException`: 试图添加已存在的用户 ID 时抛出。
- `UserIdNotFoundException`: 指定 ID 的用户不存在时抛出。
- `EqualVideoIdException`: 试图上传已存在的视频 ID 时抛出。
- `VideoIdNotFoundException`: 指定 ID 的视频不存在时抛出。
- `SelfSubscriptionException`: 用户试图关注自己时抛出。
- `DuplicateSubscriptionException`: 试图关注已经关注的用户时抛出。
- `FollowLinkNotFoundException`: 试图取消关注未关注的用户时抛出。
- `UncessException`: 试图查询两用户间最短路径但不可达时抛出。
- `InvalidAgeException`: 用户年龄不合法时抛出。

### 三、需要编写 JUnit 单元测试的方法

本次作业中，需要同学们为 `Network` 类中的 `queryMutualFollowingSum` 方法编写 JUnit 单元测试。

> 在单元测试中，你需要对 JML 的全部内容进行检查，除了检验 requires 和 ensures，还有 pure、assignable 语句等等。例如，对于一个 pure 方法，调用方法前后的状态应该一致，如果前后状态不一致，那么我们认为这不符合给定的 JML。

评测时我们会使用若干正确代码与错误代码进行测试，保证错误代码仅 **queryMutualFollowingSum** 出现错误，其余官方包要求方法均正确实现，且保证 `Video` 类不出现错误，需要同学们编写的单元测试正确判断代码的 `queryMutualFollowingSum` 方法是否出现错误。

**注意**：

在 JUnit 测评时给出的样例中，`User` 类会提供 `boolean strictEquals(UserInterface user)` 方法，`Network` 类提供 `UserInterface[] getUsers()` 方法供同学们调用。

`user1.strictEquals(usern2)` 返回一个布尔值，表示两个 `UserInterface` 对象是否相等。实现逻辑是：对于非容器的基本数据类型采用 `==`、对象类型使用 `equals()` 进行比较。设计此函数的目的是便于同学们在检査方法执行前后 `UserInterface` 对应的具体实现对象状态是否发生改变（被修改）。本方法仅仅是为了给同学提供便利，避免同学们进行大量遍历检査 `UserInterface` 对象的各属性在方法执行前后是否发生变化，同学们可以选择不调用此方法，在 JUnit 测试时使用官方包中已有的方法进行检查。

`getUsers()`返回一个 `UserInterface` 数组，表示 `Network` 中全体 `UserInterface` 元素集合，使用浅拷贝实现。

## 第四部分：设计建议

推荐各位同学在课下测试时使用 JUnit 单元测试来对自己程序的全部方法进行测试。

## 第五部分：输入输出

本次作业将会下发输入输出接口和全局测试调用程序 `Runner`，前者用于输入输出的解析和处理，后者会实例化同学们实现的类，并根据输入接口解析内容进行测试。

关于 `main` 函数内对于 `Runner` 的调用，参见以下写法。

```java
import com.oocourse.spec1.main.Runner;

public class MainClass {
    public static void main(String[] args) throws Exception {
        Runner runner = new Runner(User.class, Network.class, Video.class);
        runner.run();
    }
}
```

#### 输入输出格式

输入部分，一行或多行一条指令，形如 `op arg1 arg2 ...`，表示指令类型和参数。

输出部分，每条指令对应一行或多行输出，为指令的执行结果或发生的异常。

#### 指令格式一览

``` java
add_user id(int) age(int) name(String) 
upload_video uploaderId(int) videoId(int)
follow_user id1(int) id2(int)
unfollow_user id1(int) id2(int)
watch_video userId(int) videoId(int)
query_received_unwatched_videos userId(int)
query_up_followers_age_ratio upId(int)
query_mutual_following_sum
query_shortest_path id1(int) id2(int)
```

#### 输出说明

- 对于 `add_user`, `upload_video`, `follow_user`, `unfollow_user`, `watch_video` 指令，若执行成功，需输出 `xxx succeeded`（例如 `add_user succeeded`）。
- 对于 `query_mutual_following_sum`, `query_shortest_path` 指令，由官方包接收并输出整数结果。
- 对于 `query_received_unwatched_videos` 指令，由官方包接收并输出用户接收到但未观看的视频 ID 列表。
- 对于 `query_up_followers_age_ratio` 指令，由官方包接收并输出四个年龄段粉丝的比例，保留两位小数。

#### 样例

<div style="display:flex; width:100%; gap:20px;">
  <!-- 标准输入 -->
  <div style="flex:1;">
    <h4>标准输入</h4>
    <pre style="height:240px; overflow:auto; white-space:pre-wrap;">
add_user 1 20 Alice
add_user 2 22 Bob
add_user 3 25 Charlie
follow_user 1 2
follow_user 2 1
query_mutual_following_sum
upload_video 1 101
watch_video 2 101
query_received_unwatched_videos 2
follow_user 2 3
query_shortest_path 1 3
    </pre>
  </div>

  <!-- 标准输出 -->
  <div style="flex:1;">
    <h4>标准输出</h4>
    <pre style="height:240px; overflow:auto; white-space:pre-wrap;">
add_user succeeded
add_user succeeded
add_user succeeded
follow_user succeeded
follow_user succeeded
1
upload_video succeeded
watch_video succeeded
query_received_unwatched_videos succeeded
None
follow_user succeeded
2
    </pre>
  </div>
</div>

### 数据范围

#### 公测数据限制

- 指令条数不多于 $10000$ 条。
- 所有 $id$ 在 `int` 范围内。
- $name$ 为字符串，长度 $|name|$ 满足不小于 $1 \le |name| \le 100$
- $0 < age \le 200$ 且为整数。

#### 互测数据限制

- 指令条数不多于 $3000$ 条。

### 测试模式

公测和互测都将使用指令的形式模拟容器的各种状态，从而测试各个类的实现正确性，即是否满足 JML 规格的定义或者指导书描述。

**可以认为，只要所要求的所有类的具体实现严格满足 JML，同时异常处理符合指导书和官方包的描述，就能保证正确性，但是不保证满足时间限制。**

任何满足规则的输入，程序都应该保证不会异常退出，如果出现问题即视为未通过该测试点。

## 第六部分：补充说明

### 关于提交代码部分的文件结构：

src 目录下包含主入口类（例如 `MainClass.java`），同学们实现官方包接口的类（`Network`，`User`，`Video`）以及同学们可能自行设计的辅助类。

**请注意：提交的时候请不要在 src 目录下包含官方包**，同学们自己实现的官方包接口的类的命名还请按照（`Network`，`User`，`Video`）命名，并直接放在 src 目录下，不要嵌套子目录，否则和测试程序一起编译的时候会无法通过。

test 目录下设置测试类（例如 Test.java），以及同学们可能自己设计的辅助类。

### 关于评测机制：

受到系统限制，我们只能统一编译 `src` 文件夹和 `test` 文件夹，同学提交代码之前请确保 `src` 和 `test` 文件夹下本地的静态编译能通过。

### 关于编译的说明：

由于评测是 src 文件夹和 test 文件夹统一编译的，同学们如果在 test 文件夹中的测试类使用了课程组提供的 `getUsers` 和 `strictEquals`方法，请在 src文件夹下的 `Network` 类中实现 `getUsers` 方法，在 `User` 类中实现 `strictEquals` 方法（不必正确实现方法，写任意能通过编译的内容都可）。

---

## 第七部分：提示与警示

### 一、提示

- 请同学们参考源码，注意本单元中一切叙述的讨论范围实际限定于全局唯一的 Network 实例中
- 本次作业中可以自行组织代码结构。任意新增 java 代码文件。只需要保证题目要求的几个类的继承与实现即可。
- **关于本次作业容器类的设计具体细节，本指导书中均不会进行过多描述，请自行去官方包仓库中查看接口的规格，并依据规格进行功能的具体实现。**
- 仓库地址：[第九次作业公共仓库](https://gitlab-oo.e1.buaa.edu.cn/2026_oo_public/officialpackage/u3_hw9)
  
### 二、警示

- **请勿试图对官方接口进行操作**。此外，在互测环节中，如果发现有人试图 hack 输出接口，请联系助教，经核实后，**将直接作为无效作业处理**。 