package com.oocourse.spec2.exceptions;

/**
 * {@code VideoUnwatchedException} 类用于表示当用户尝试对未观看的视频点赞、投币或转发时抛出的异常。
 * 该异常类包含两个整型参数 {@code id1} 和 {@code id2}，分别表示触发异常的用户 ID 和 视频 ID。
 *
 * <p>异常统计信息的格式为：vu-{@code x}, {@code id1}-{@code y}, {@code id2}-{@code z}，
 * 其中 {@code x} 为此类异常发生的总次数，{@code y} 为 {@code id1} 触发此类异常的次数，
 * {@code z} 为 {@code id2} 触发此类异常的次数。</p>
 */
public class VideoUnwatchedException extends MyException {
    private static final ErrorCount errorCount = new ErrorCount();
    private static int count = 0;
    private final int id1;
    private final int id2;

    /**
     * 构造一个新的 {@code VideoUnwatchedException} 实例。
     *
     *
     * @param id1 触发异常的用户 ID
     * @param id2 触发异常的视频 ID
     */
    public VideoUnwatchedException(int id1, int id2) {
        this.id1 = id1;
        this.id2 = id2;
        count++;
        errorCount.putError(id1);
        errorCount.putError(id2);
    }

    /**
     * 输出异常的统计信息到标准输出。
     * 格式为：vu-{@code x}, {@code id1}-{@code y}, {@code id2}-{@code z}，* 其中 {@code x} 为此类异常发生的总次数，{@code y} 为 {@code id1} 触发此类异常的次数，
     * {@code z} 为 {@code id2} 触发此类异常的次数。
     */
    public void print() {
        System.out.println("vu-" + count + ", " + id1 + "-" + errorCount.getIdCount(id1) + ", " + id2 + "-" + errorCount.getIdCount(id2));
    }
}
