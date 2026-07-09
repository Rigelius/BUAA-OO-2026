package com.oocourse.spec1.main;

import java.util.List;

public interface UserInterface {

    /*@ public instance model int id;
      @ public instance model non_null String name;
      @ public instance model int age;
      @ public instance model non_null UserInterface[] following;
      @ public instance model non_null UserInterface[] followers;
      @ public instance model non_null int[] receivedVideos;
      @*/

    /*@ invariant (\forall int i,j; 0 <= i && i < j && j < following.length;
      @               !following[i].equals(following[j])) &&
      @           (\forall int i,j; 0 <= i && i < j && j < followers.length;
      @               !followers[i].equals(followers[j]))
      @*/
    
    //@ ensures \result == id;
    public /*@ pure @*/ int getId();
    
    //@ ensures \result == name;
    public /*@ pure @*/ String getName();
    
    //@ ensures \result == age;
    public /*@ pure @*/ int getAge();
    
    /*@ public normal_behavior
      @ assignable \nothing;
      @ ensures \result == (\exists int i; 0 <= i && i < following.length;
      @                     following[i].getId() == user.getId());
      @*/
    public /*@ pure @*/ boolean isFollowing(UserInterface user);

    /*@ public normal_behavior
      @ assignable \nothing;
      @ ensures \result == (\exists int i; 0 <= i && i < followers.length;
      @                     followers[i].getId() == user.getId());
      @*/
    public /*@ pure @*/ boolean containsFollower(UserInterface user);

    /*@ public normal_behavior
      @ assignable \nothing;
      @ ensures \result == (\exists int i; 0 <= i && i < receivedVideos.length;
      @                     receivedVideos[i] == video.getId());
      @*/
    public /*@ pure @*/ boolean hasReceivedVideo(VideoInterface video);

    /*@ public normal_behavior
      @ requires followers.length == 0;
      @ assignable \nothing;
      @ ensures \result != null && \result.length == 4;
      @ ensures (\forall int i; 0 <= i && i < 4; \result[i] == 0.0);
      @ also
      @ public normal_behavior
      @ requires followers.length > 0;
      @ assignable \nothing;
      @ ensures \result != null && \result.length == 4;
      @ ensures \result[0] == 1.0 * (\num_of int k; 0 <= k < followers.length; followers[k].getAge() <= 16) / followers.length;
      @ ensures \result[1] == 1.0 * (\num_of int k; 0 <= k < followers.length; followers[k].getAge() >= 17 && followers[k].getAge() <= 30) / followers.length;
      @ ensures \result[2] == 1.0 * (\num_of int k; 0 <= k < followers.length; followers[k].getAge() >= 31 && followers[k].getAge() <= 45) / followers.length;
      @ ensures \result[3] == 1.0 * (\num_of int k; 0 <= k < followers.length; followers[k].getAge() >= 46) / followers.length;
      @*/
    public /*@ pure @*/ double[] queryAgeRatio();

    /*@ public normal_behavior
      @ assignable \nothing;
      @ ensures \result != null;
      @ ensures (\forall int i; 0 <= i && i < receivedVideos.length && i <= 4;
      @           \result.contains(receivedVideos[i]) && \result.get(i) == receivedVideos[i]);
      @ ensures \result.size() == ((receivedVideos.length < 5) ? receivedVideos.length: 5);
     */
    public /*@ pure @*/ List<Integer> queryReceivedUnwatchedVideos();
    
    /*@ public normal_behavior
      @ requires obj != null && obj instanceof UserInterface;
      @ assignable \nothing;
      @ ensures \result == (((UserInterface) obj).getId() == id);
      @ also
      @ public normal_behavior
      @ requires obj == null || !(obj instanceof UserInterface);
      @ assignable \nothing;
      @ ensures \result == false;
      @*/
    public /*@ pure @*/ boolean equals(Object obj);
}